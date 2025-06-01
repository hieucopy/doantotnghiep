from django.contrib import admin
from django.shortcuts import render, redirect
from django.urls import path
from .models import ChurnPrediction, ModelEvaluation
from .ml_model import ChurnPredictionModel
from users.models import CustomUser
from django.db.models import Sum, Avg, Count, Max, F
from services.models import ServiceUsage, ServicePlan
from support.models import SupportTicket
from datetime import datetime, timedelta
import os
import numpy as np
from sklearn.metrics import roc_curve, confusion_matrix
from sklearn.model_selection import learning_curve
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import pytz
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from django.contrib import messages
from django.utils import timezone
from django.db import connection

class TelecomAdminSite(admin.AdminSite):
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('churn-prediction/evaluate/', 
                 self.admin_view(ModelEvaluationView.as_view()), 
                 name='churn_prediction_evaluate'),
        ]
        return custom_urls + urls

    def index(self, request, extra_context=None):
        # Lấy thống kê cơ bản
        stats = {
            'total_users': CustomUser.objects.count(),
            'total_services': ServiceUsage.objects.filter(
                start_date__gte=datetime.now() - timedelta(days=30)
            ).count(),
            'total_tickets': SupportTicket.objects.count(),
        }
        
        extra_context = extra_context or {}
        extra_context.update(stats)
        
        return super().index(request, extra_context)

# Tạo instance của custom admin site
admin_site = TelecomAdminSite(name='admin')

# Đăng ký tất cả các model với custom admin site
admin_site.register(CustomUser)
admin_site.register(ServiceUsage)
admin_site.register(ServicePlan)
admin_site.register(SupportTicket)

@admin.register(ChurnPrediction, site=admin_site)
class ChurnPredictionAdmin(admin.ModelAdmin):
    list_display = ['user', 'churn_probability', 'prediction_date']
    actions = ['train_model', 'predict_churn']

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('predict/', self.admin_site.admin_view(self.churn_predict_view), name='churn_prediction_churnprediction_predict'),
            path('train/', self.admin_site.admin_view(self.churn_train_view), name='churn_prediction_churnprediction_train'),
            path('customer-insights/', self.admin_site.admin_view(self.customer_insights_view), name='churn_prediction_churnprediction_customer_insights'),
            path('model-insights/', self.admin_site.admin_view(self.model_insights_view), name='churn_prediction_churnprediction_model_insights'),
        ]
        return custom_urls + urls

    def churn_predict_view(self, request):
        if not request.user.is_superuser:
            self.message_user(request, "Only superusers can access this page.", level='error')
            return redirect('admin:index')

        context = {
            'title': 'Churn Prediction Analysis',
            'churn_probability': None,
            'user_info': None
        }

        if request.method == 'POST':
            user_id = request.POST.get('user_id')
            try:
                model = ChurnPredictionModel()
                user = CustomUser.objects.get(id=user_id)
                
                # Lấy thông tin chi tiết về người dùng
                # Thông tin cơ bản
                user_info = {
                    'username': user.username,
                    'email': user.email,
                    'date_joined': user.date_joined,
                    'last_login': user.last_login,
                }
                
                # Thông tin sử dụng dịch vụ
                service_stats = ServiceUsage.objects.filter(user=user).aggregate(
                    total_packages=Count('id'),
                    total_spent=Sum('spent_amount'),
                    avg_data_usage=Avg('data_usage'),
                    avg_call_minutes=Avg('call_minutes'),
                    avg_sms_used=Avg('sms_used')
                )
                user_info.update(service_stats)
                
                # Thông tin hỗ trợ
                support_stats = SupportTicket.objects.filter(user=user).aggregate(
                    total_tickets=Count('id'),
                    avg_rating=Avg('rating'),
                    last_ticket_date=Max('created_at')
                )
                user_info.update(support_stats)
                
                # Tính thời gian phản hồi trung bình (tính bằng giờ)
                support_tickets = SupportTicket.objects.filter(user=user).exclude(response__isnull=True)
                if support_tickets.exists():
                    total_hours = 0
                    for ticket in support_tickets:
                        if ticket.updated_at and ticket.created_at:
                            delta = ticket.updated_at - ticket.created_at
                            total_hours += delta.total_seconds() / 3600
                    user_info['avg_response_time'] = round(total_hours / support_tickets.count(), 1)
                else:
                    user_info['avg_response_time'] = 0
                
                # Dự đoán churn
                churn_probability = model.predict(user_id) * 100  # Chuyển đổi sang phần trăm
                
                # Không cần lưu lại vì model.predict đã tự lưu
                context.update({
                    'churn_probability': churn_probability,
                    'user_info': user_info,
                    'prediction_date': datetime.now()
                })
                
                # Thông báo thành công
                self.message_user(
                    request,
                    f"Successfully predicted churn probability for {user.username}",
                    level='success'
                )
                
            except CustomUser.DoesNotExist:
                self.message_user(
                    request,
                    f"User with ID {user_id} not found",
                    level='error'
                )
            except ValueError as ve:
                self.message_user(
                    request,
                    f"Validation error: {str(ve)}",
                    level='error'
                )
            except Exception as e:
                self.message_user(
                    request,
                    f"Prediction error: {str(e)}",
                    level='error'
                )
        
        return render(request, 'admin/churn_predict.html', context)

    def churn_train_view(self, request):
        if not request.user.is_superuser:
            self.message_user(request, "Only superusers can access this page.")
            return redirect('admin:index')
        
        # Thêm today_date vào context để hiển thị ngày mặc định
        context = {
            'title': 'Model Training',
            'today_date': datetime.now(pytz.UTC)
        }
        
        if request.method == 'POST':
            try:
                reference_date = request.POST.get('reference_date')
                if not reference_date:
                    raise ValueError("Reference date is required")
                
                reference_date = datetime.strptime(reference_date, '%Y-%m-%d').replace(tzinfo=pytz.UTC)
                test_size = float(request.POST.get('test_size', 0.2))
                n_estimators = int(request.POST.get('n_estimators', 100))
                max_depth = int(request.POST.get('max_depth', 10))
                
                if test_size <= 0 or test_size >= 1:
                    raise ValueError("Test size phải nằm trong khoảng (0, 1)")
                if n_estimators <= 0 or max_depth <= 0:
                    raise ValueError("n_estimators và max_depth phải lớn hơn 0")
                
                model = ChurnPredictionModel()
                metrics = model.train(reference_date=reference_date, test_size=test_size, 
                                    n_estimators=n_estimators, max_depth=max_depth)
                self.message_user(request, f"Model trained successfully. Metrics: {metrics}")
            except ValueError as ve:
                self.message_user(request, f"Lỗi xác thực: {str(ve)}")
            except Exception as e:
                self.message_user(request, f"Error training model: {str(e)}")
        
        return render(request, 'admin/churn_train.html', context)

    def train_model(self, request, queryset):
        model = ChurnPredictionModel()
        try:
            metrics = model.train()
            self.message_user(request, f"Model trained successfully. Metrics: {metrics}")
        except Exception as e:
            self.message_user(request, f"Error training model: {str(e)}")

    def predict_churn(self, request, queryset):
        model = ChurnPredictionModel()
        for prediction in queryset:
            try:
                user = prediction.user
                # Gọi predict sẽ tự động lưu dự đoán mới nhất
                churn_probability = model.predict(user.id)
                self.message_user(request, f"Dự đoán cho {user.username}: {churn_probability:.2%}")
            except Exception as e:
                self.message_user(request, f"Lỗi dự đoán cho {user.username}: {str(e)}")

    def customer_insights_view(self, request):
        if not request.user.is_superuser:
            self.message_user(request, "Only superusers can access this page.", level='error')
            return redirect('admin:index')

        context = {
            'title': 'Customer Insights',
            'customer': None,
            'service_history': None,
            'churn_factors': None
        }

        if request.method == 'GET':
            search_type = request.GET.get('search_type', 'id')
            search_query = request.GET.get('search_query')

            if search_query:
                try:
                    # Tìm kiếm khách hàng
                    if search_type == 'id':
                        user = CustomUser.objects.get(id=search_query)
                    elif search_type == 'username':
                        user = CustomUser.objects.get(username=search_query)
                    else:  # email
                        user = CustomUser.objects.get(email=search_query)

                    # Lấy thông tin cơ bản
                    customer = {
                        'username': user.username,
                        'email': user.email,
                        'date_joined': user.date_joined,
                        'last_login': user.last_login,
                    }

                    # Thống kê sử dụng dịch vụ
                    service_stats = ServiceUsage.objects.filter(user=user).aggregate(
                        total_packages=Count('id'),
                        total_spent=Sum('spent_amount'),
                        avg_data_usage=Avg('data_usage'),
                        avg_call_minutes=Avg('call_minutes'),
                        avg_sms_used=Avg('sms_used')
                    )
                    customer.update(service_stats)

                    # Thống kê hỗ trợ
                    support_stats = SupportTicket.objects.filter(user=user).aggregate(
                        total_tickets=Count('id'),
                        avg_rating=Avg('rating'),
                        last_ticket_date=Max('created_at')
                    )
                    customer.update(support_stats)

                    # Tính thời gian phản hồi trung bình (tính bằng giờ)
                    support_tickets = SupportTicket.objects.filter(user=user).exclude(response__isnull=True)
                    if support_tickets.exists():
                        total_hours = 0
                        for ticket in support_tickets:
                            if ticket.updated_at and ticket.created_at:
                                delta = ticket.updated_at - ticket.created_at
                                total_hours += delta.total_seconds() / 3600
                        customer['avg_response_time'] = round(total_hours / support_tickets.count(), 1)
                    else:
                        customer['avg_response_time'] = 0

                    # Lịch sử sử dụng dịch vụ
                    service_history = ServiceUsage.objects.filter(user=user).select_related('service_plan').order_by('-start_date')

                    # Phân tích các yếu tố ảnh hưởng đến churn
                    model = ChurnPredictionModel()
                    # Gọi predict sẽ tự động lưu dự đoán mới nhất
                    churn_probability = model.predict(user.id) * 100  # Chuyển đổi sang phần trăm
                    customer['churn_probability'] = round(churn_probability, 1)
                    
                    # Lấy feature importance từ model
                    feature_importance = model.get_feature_importance()
                    
                    # Phân tích các yếu tố chính ảnh hưởng đến churn
                    churn_factors = []
                    for feature, importance in feature_importance.items():
                        if importance > 0.05:  # Chỉ xem xét các yếu tố có tầm quan trọng > 5%
                            factor = {
                                'name': feature.replace('_', ' ').title(),
                                'importance': importance,
                                'value': getattr(customer, feature, 0),
                                'impact': 'high' if importance > 0.15 else 'medium' if importance > 0.1 else 'low'
                            }
                            
                            # Thêm mô tả cho từng yếu tố
                            if feature == 'months_since_joined':
                                factor['description'] = f"Customer has been with us for {customer.get('months_since_joined', 0):.1f} months"
                            elif feature == 'num_service_plans':
                                factor['description'] = f"Customer has used {customer.get('total_packages', 0)} service plans"
                            elif feature == 'total_spent':
                                factor['description'] = f"Customer has spent {customer.get('total_spent', 0):,.0f} VND"
                            elif feature == 'avg_rating':
                                factor['description'] = f"Customer's average support rating is {customer.get('avg_rating', 0):.1f}/5.0"
                            elif feature == 'total_savings':
                                factor['description'] = f"Customer has saved {customer.get('total_savings', 0):,.0f} VND through promotions"
                            else:
                                factor['description'] = f"Current value: {customer.get(feature, 0)}"

                            churn_factors.append(factor)

                    # Sắp xếp các yếu tố theo tầm quan trọng
                    churn_factors.sort(key=lambda x: x['importance'], reverse=True)

                    context.update({
                        'customer': customer,
                        'service_history': service_history,
                        'churn_factors': churn_factors
                    })

                except CustomUser.DoesNotExist:
                    self.message_user(
                        request,
                        f"User not found with the provided {search_type}",
                        level='error'
                    )
                except Exception as e:
                    self.message_user(
                        request,
                        f"Error retrieving customer insights: {str(e)}",
                        level='error'
                    )

        return render(request, 'admin/customer_insights.html', context)

    def model_insights_view(self, request):
        if not request.user.is_superuser:
            self.message_user(request, "Only superusers can access this page.", level='error')
            return redirect('admin:index')

        try:
            model = ChurnPredictionModel()
            
            # Lấy thông tin model
            model_info = {
                'training_date': datetime.fromtimestamp(os.path.getmtime(model.model_path)) if os.path.exists(model.model_path) else None,
                'test_size': 0.2,  # Default value
                'n_estimators': model.model.n_estimators if model.model else 100,
                'max_depth': model.model.max_depth if model.model else 10
            }

            # Lấy metrics từ lần training gần nhất
            df = model._load_and_prepare_data()
            if not df.empty:
                X = df.drop(columns=['user_id', 'churned'])
                y = df['churned'].astype(int)
                
                X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
                X_test_scaled = model.scaler.transform(X_test)
                y_pred = model.model.predict(X_test_scaled)
                y_pred_proba = model.model.predict_proba(X_test_scaled)[:, 1]

                # Tính toán metrics
                metrics = {
                    'accuracy': accuracy_score(y_test, y_pred),
                    'precision': precision_score(y_test, y_pred),
                    'recall': recall_score(y_test, y_pred),
                    'f1_score': f1_score(y_test, y_pred)
                }

                # Tính ROC curve
                fpr, tpr, _ = roc_curve(y_test, y_pred_proba)
                roc_curve_data = {
                    'fpr': fpr.tolist(),
                    'tpr': tpr.tolist(),
                    'random': np.linspace(0, 1, len(fpr)).tolist()
                }

                # Tính confusion matrix
                cm = confusion_matrix(y_test, y_pred)
                confusion_matrix_data = {
                    'tn': int(cm[0, 0]),
                    'fp': int(cm[0, 1]),
                    'fn': int(cm[1, 0]),
                    'tp': int(cm[1, 1])
                }

                # Tính learning curves
                train_sizes, train_scores, val_scores = learning_curve(
                    model.model, X, y, cv=5, n_jobs=-1,
                    train_sizes=np.linspace(0.1, 1.0, 10)
                )
                learning_curves_data = {
                    'train_sizes': train_sizes.tolist(),
                    'train_scores': train_scores.mean(axis=1).tolist(),
                    'val_scores': val_scores.mean(axis=1).tolist()
                }

                # Lấy feature importance
                feature_importance = []
                for feature, importance in zip(X.columns, model.model.feature_importances_):
                    feature_importance.append({
                        'name': feature.replace('_', ' ').title(),
                        'importance': float(importance)
                    })
                feature_importance.sort(key=lambda x: x['importance'], reverse=True)

                context = {
                    'title': 'Model Insights',
                    'model_info': model_info,
                    'metrics': metrics,
                    'roc_curve': roc_curve_data,
                    'confusion_matrix': confusion_matrix_data,
                    'learning_curves': learning_curves_data,
                    'feature_importance': feature_importance
                }
            else:
                raise ValueError("No training data available")

        except Exception as e:
            self.message_user(
                request,
                f"Error retrieving model insights: {str(e)}",
                level='error'
            )
            context = {
                'title': 'Model Insights',
                'error': str(e)
            }

        return render(request, 'admin/model_insights.html', context)

@admin.register(ModelEvaluation, site=admin_site)
class ModelEvaluationAdmin(admin.ModelAdmin):
    list_display = ('reference_date', 'evaluation_date', 'time_elapsed_days', 
                   'accuracy', 'precision', 'recall', 'f1_score', 'roc_auc',
                   'total_users', 'actual_churns', 'predicted_churns')
    list_filter = ('reference_date', 'evaluation_date')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'reference_date'

    def has_add_permission(self, request):
        return False  # Không cho phép thêm thủ công

    def has_change_permission(self, request, obj=None):
        return False  # Không cho phép sửa thủ công

@method_decorator(staff_member_required, name='dispatch')
class ModelEvaluationView(TemplateView):
    template_name = 'admin/churn_evaluate.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Đánh giá độ chính xác mô hình'
        context['today_date'] = timezone.now()
        
        # Lấy danh sách các lần đánh giá gần đây
        context['recent_evaluations'] = ModelEvaluation.objects.all()[:5]
        
        # Lấy danh sách các ngày tham chiếu có dự đoán
        try:
            # Sử dụng raw SQL để lấy các ngày tham chiếu duy nhất
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT DISTINCT DATE(prediction_date) as ref_date
                    FROM churn_prediction_churnprediction
                    ORDER BY ref_date DESC
                    LIMIT 10
                """)
                reference_dates = [row[0] for row in cursor.fetchall()]
                context['reference_dates'] = reference_dates
        except Exception as e:
            print(f"Lỗi khi lấy danh sách ngày tham chiếu: {e}")
            context['reference_dates'] = []
        
        return context

    def post(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, 'Bạn không có quyền thực hiện thao tác này')
            return redirect('admin:index')

        try:
            # Lấy ngày tham chiếu từ form
            reference_date_str = request.POST.get('reference_date')
            if not reference_date_str:
                raise ValueError('Vui lòng chọn ngày tham chiếu')
            
            reference_date = datetime.strptime(reference_date_str, '%Y-%m-%d')
            reference_date = timezone.make_aware(reference_date, timezone=pytz.UTC)
            
            # Lấy ngày đánh giá (mặc định là ngày hiện tại)
            evaluation_date = timezone.now()
            
            # Thực hiện đánh giá
            model = ChurnPredictionModel()
            metrics = model.evaluate_model_accuracy(reference_date, evaluation_date)
            
            messages.success(request, f'Đã đánh giá mô hình thành công. Accuracy: {metrics["accuracy"]:.3f}')
            
        except ValueError as e:
            messages.error(request, f'Lỗi xác thực: {str(e)}')
        except Exception as e:
            messages.error(request, f'Lỗi: {str(e)}')
        
        return redirect('admin:index')

# Thêm link vào admin index
admin_site.index_template = 'admin/custom_index.html'