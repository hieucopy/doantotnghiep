from django.contrib import admin
from django.shortcuts import render, redirect
from django.urls import path
from .models import ChurnPrediction, ModelEvaluation
from .ml_model import ChurnPredictionModel
from users.models import CustomUser
from django.db.models import Sum, Avg, Count, Max, F, Q, FloatField, Subquery, OuterRef
from django.db.models.functions import Coalesce
from services.models import ServiceUsage, ServicePlan, Promotion
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
from django.views.generic import TemplateView, ListView
from django.contrib import messages
from django.utils import timezone
from django.db import connection
from django.core.paginator import Paginator
from django.http import JsonResponse
from services.admin import ServicePlanAdmin, ServiceUsageAdmin, PromotionAdmin
from users.admin import CustomUserAdmin, CustomerProfileAdmin
from support.admin import SupportTicketAdmin
import json

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
admin_site.register(CustomUser, CustomUserAdmin)
admin_site.register(ServiceUsage, ServiceUsageAdmin)
admin_site.register(ServicePlan, ServicePlanAdmin)
admin_site.register(SupportTicket, SupportTicketAdmin)
admin_site.register(Promotion, PromotionAdmin)

@admin.register(ChurnPrediction, site=admin_site)
class ChurnPredictionAdmin(admin.ModelAdmin):
    list_display = ['user', 'churn_probability', 'prediction_date']
    actions = ['train_model', 'predict_churn']

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('predict/', self.admin_site.admin_view(self.churn_predict_view), name='churn_prediction_churnprediction_predict'),
            path('train/', self.admin_site.admin_view(self.churn_train_view), name='churn_prediction_churnprediction_train'),
            path('prepare-data/', self.admin_site.admin_view(self.prepare_data_view), name='churn_prediction_churnprediction_prepare_data'),
            path('customer-insights/', self.admin_site.admin_view(self.customer_list_view), name='churn_prediction_churnprediction_customer_list'),
            path('customer-insights/<int:user_id>/', self.admin_site.admin_view(self.customer_detail_view), name='churn_prediction_churnprediction_customer_detail'),
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
                result = model.predict_user_churn(user_id)
                churn_probability = result['churn_probability'] * 100  # Chuyển đổi sang phần trăm
                
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
                
                # Nếu là nút "Huấn luyện mô hình"
                if 'train' in request.POST:
                    # Kiểm tra và chuyển đổi các tham số huấn luyện
                    test_size = float(request.POST.get('test_size', 0.2))
                    n_estimators = int(request.POST.get('n_estimators', 100))
                    max_depth = int(request.POST.get('max_depth', 10))
                    
                    if test_size <= 0 or test_size >= 1:
                        raise ValueError("Test size phải nằm trong khoảng (0, 1)")
                    if n_estimators <= 0 or max_depth <= 0:
                        raise ValueError("n_estimators và max_depth phải lớn hơn 0")
                    
                    model = ChurnPredictionModel()
                    metrics = model.train(
                        reference_date=reference_date,
                        test_size=test_size,
                        n_estimators=n_estimators,
                        max_depth=max_depth
                    )
                    context['metrics'] = metrics
                    self.message_user(request, "Model trained successfully!", level='success')
                
                # Nếu là nút "Lưu dự đoán cho tất cả người dùng"
                elif 'save_predictions' in request.POST:
                    model = ChurnPredictionModel()
                    
                    # Kiểm tra xem model đã được huấn luyện chưa
                    if not os.path.exists(model.model_path):
                        raise ValueError("Model chưa được huấn luyện. Vui lòng huấn luyện model trước khi lưu dự đoán.")
                    
                    # Xóa tất cả dự đoán cũ
                    ChurnPrediction.objects.all().delete()
                    
                    # Lấy danh sách tất cả users
                    users = CustomUser.objects.values_list('id', flat=True)
                    total_users = len(users)
                    predictions_saved = 0
                    errors = 0
                    batch_size = 100  # Tăng batch size lên để xử lý nhiều user hơn mỗi lần
                    
                    # Xử lý theo batch
                    for i in range(0, total_users, batch_size):
                        batch_user_ids = list(users[i:i+batch_size])
                        
                        try:
                            # Dự đoán cho cả batch
                            batch_predictions = model.predict_batch_users(
                                user_ids=batch_user_ids,
                                reference_date=reference_date
                            )
                            
                            # Tạo danh sách các đối tượng ChurnPrediction
                            predictions_to_create = [
                                ChurnPrediction(
                                    user_id=user_id,
                                    prediction_date=reference_date,
                                    churn_probability=pred_data['churn_probability']
                                )
                                for user_id, pred_data in batch_predictions.items()
                            ]
                            
                            # Lưu tất cả dự đoán trong batch
                            ChurnPrediction.objects.bulk_create(predictions_to_create)
                            predictions_saved += len(predictions_to_create)
                            
                        except Exception as e:
                            errors += len(batch_user_ids)
                            self.message_user(
                                request,
                                f"Error processing batch {i//batch_size + 1}: {str(e)}",
                                level='warning'
                            )
                        
                        # Hiển thị tiến trình
                        progress = (i + len(batch_user_ids)) / total_users * 100
                        self.message_user(
                            request,
                            f"Processing... {progress:.1f}% complete ({predictions_saved} predictions saved, {errors} errors)",
                            level='info'
                        )
                    
                    # Hiển thị thông báo tổng kết
                    if predictions_saved > 0:
                        self.message_user(
                            request,
                            f"Successfully saved predictions for {predictions_saved} users! ({errors} errors)",
                            level='success'
                        )
                    else:
                        self.message_user(
                            request,
                            f"No predictions were saved. Please check the errors above.",
                            level='error'
                        )
            
            except ValueError as ve:
                self.message_user(request, f"Validation error: {str(ve)}", level='error')
            except Exception as e:
                self.message_user(request, f"Error: {str(e)}", level='error')
        
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
                # Gọi predict_user_churn thay vì predict
                result = model.predict_user_churn(user.id)
                churn_probability = result['churn_probability']
                self.message_user(request, f"Dự đoán cho {user.username}: {churn_probability:.2%}")
            except Exception as e:
                self.message_user(request, f"Lỗi dự đoán cho {user.username}: {str(e)}")

    def customer_list_view(self, request):
        if not request.user.is_superuser:
            self.message_user(request, "Only superusers can access this page.", level='error')
            return redirect('admin:index')

        # Kiểm tra nếu đây là tìm kiếm chi tiết một khách hàng
        search_type = request.GET.get('search_type')
        search_query = request.GET.get('search_query')
        
        # Nếu có tìm kiếm cụ thể và đủ thông tin, chuyển sang trang chi tiết
        if search_type and search_query and search_query.strip():
            try:
                user = None
                if search_type == 'id':
                    try:
                        user_id = int(search_query)
                        user = CustomUser.objects.get(id=user_id)
                    except (ValueError, CustomUser.DoesNotExist):
                        self.message_user(request, f"Không tìm thấy người dùng với ID: {search_query}", level='error')
                elif search_type == 'username':
                    try:
                        user = CustomUser.objects.get(username=search_query)
                    except CustomUser.DoesNotExist:
                        self.message_user(request, f"Không tìm thấy người dùng với username: {search_query}", level='error')
                elif search_type == 'email':
                    try:
                        user = CustomUser.objects.get(email=search_query)
                    except CustomUser.DoesNotExist:
                        self.message_user(request, f"Không tìm thấy người dùng với email: {search_query}", level='error')
                
                if user:
                    return redirect('admin:churn_prediction_churnprediction_customer_detail', user_id=user.id)
                
            except Exception as e:
                self.message_user(request, f"Lỗi khi tìm kiếm: {str(e)}", level='error')
        
        # Các tham số filter và sắp xếp
        filter_search = request.GET.get('search', '')
        service_plan = request.GET.get('service_plan', '')
        churn_risk = request.GET.get('churn_risk', '')
        sort_by = request.GET.get('sort_by', '-churn_probability')
        page = request.GET.get('page', 1)

        # Base queryset - hiển thị tất cả người dùng
        queryset = CustomUser.objects.annotate(
            latest_churn_prob=Coalesce(
                Subquery(
                    ChurnPrediction.objects.filter(
                        user=OuterRef('id')
                    ).order_by('-prediction_date').values('churn_probability')[:1]
                ),
                0,
                output_field=FloatField()
            ) * 100,  # Chuyển đổi thành phần trăm
            total_spent=Coalesce(
                Sum('service_usages__spent_amount'),
                0,
                output_field=FloatField()
            ),
            active_services=Count(
                'service_usages',
                filter=Q(
                    service_usages__end_date__gte=timezone.now(),
                    service_usages__is_active=True
                )
            ),
            avg_rating=Coalesce(
                Avg('support_tickets__rating'),
                0,
                output_field=FloatField()
            ),
            last_activity=Max(
                'service_usages__start_date'
            )
        )

        # Áp dụng các bộ lọc
        if filter_search:
            queryset = queryset.filter(
                Q(username__icontains=filter_search) |
                Q(email__icontains=filter_search)
            )

        if service_plan:
            queryset = queryset.filter(
                service_usages__service_plan__name=service_plan,
                service_usages__is_active=True
            )

        if churn_risk:
            if churn_risk == 'high':
                queryset = queryset.filter(latest_churn_prob__gte=70)
            elif churn_risk == 'medium':
                queryset = queryset.filter(latest_churn_prob__range=(30, 70))
            elif churn_risk == 'low':
                queryset = queryset.filter(latest_churn_prob__lt=30)

        # Sắp xếp
        if sort_by:
            if sort_by == 'username':
                queryset = queryset.order_by('username')
            elif sort_by == '-churn_probability':
                queryset = queryset.order_by('-latest_churn_prob')
            elif sort_by == 'total_spent':
                queryset = queryset.order_by('-total_spent')
            elif sort_by == 'last_activity':
                queryset = queryset.order_by('-last_activity')

        # Phân trang
        paginator = Paginator(queryset, 50)  # 50 users per page
        customers = paginator.get_page(page)

        # Lấy danh sách các gói cước để filter
        service_plans = ServicePlan.objects.filter(is_active=True).values_list('name', flat=True)

        context = {
            'title': 'Danh sách khách hàng',
            'customers': customers,
            'service_plans': service_plans,
            'current_filters': {
                'search': filter_search,
                'service_plan': service_plan,
                'churn_risk': churn_risk,
                'sort_by': sort_by
            }
        }

        # Render trang customer_list.html thay vì customer_insights.html
        return render(request, 'admin/customer_list.html', context)

    def customer_detail_view(self, request, user_id):
        """Hiển thị chi tiết thông tin của một khách hàng"""
        if not request.user.is_superuser:
            self.message_user(request, "Only superusers can access this page.", level='error')
            return redirect('admin:index')

        try:
            user = CustomUser.objects.get(id=user_id)

            # Thông tin cơ bản
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

            # Tính thời gian phản hồi trung bình
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

            # Phân tích xu hướng sử dụng
            usage_trends = self._analyze_usage_trends(user)

            # Phân tích các yếu tố ảnh hưởng đến churn
            model = ChurnPredictionModel()
            try:
                # Lấy dự đoán churn gần nhất từ database
                latest_prediction = ChurnPrediction.objects.filter(user=user).order_by('-prediction_date').first()
                if latest_prediction:
                    churn_probability = float(latest_prediction.churn_probability) * 100
                else:
                    # Nếu không có dự đoán nào trong database, tạo mới
                    result = model.predict_user_churn(user.id)
                    churn_probability = float(result['churn_probability']) * 100
                customer['churn_probability'] = round(churn_probability, 1)
            except Exception as e:
                self.message_user(request, f"Lỗi khi dự đoán churn: {str(e)}", level='warning')
                customer['churn_probability'] = 0

            feature_importance = model.get_feature_importance()
            churn_factors = self._analyze_churn_factors(customer, feature_importance)

            context = {
                'title': f'Customer Details - {user.username}',
                'customer': customer,
                'service_history': service_history,
                'usage_trends': usage_trends,
                'churn_factors': churn_factors,
                'support_tickets': support_tickets
            }

            return render(request, 'admin/customer_insights.html', context)

        except CustomUser.DoesNotExist:
            self.message_user(request, f"User with ID {user_id} not found", level='error')
            return redirect('admin:churn_prediction_churnprediction_customer_list')
        except Exception as e:
            self.message_user(request, f"Error retrieving customer details: {str(e)}", level='error')
            return redirect('admin:churn_prediction_churnprediction_customer_list')

    def _analyze_usage_trends(self, user):
        """Phân tích xu hướng sử dụng dịch vụ của khách hàng"""
        now = timezone.now()
        three_months_ago = now - timedelta(days=90)
        six_months_ago = now - timedelta(days=180)

        # Lấy dữ liệu sử dụng trong 6 tháng gần nhất
        recent_usage = ServiceUsage.objects.filter(
            user=user,
            start_date__gte=six_months_ago
        ).order_by('start_date')

        # Phân tích xu hướng theo tháng
        monthly_trends = {}
        for usage in recent_usage:
            # Đảm bảo start_date có timezone
            if usage.start_date.tzinfo is None:
                start_date = timezone.make_aware(usage.start_date, timezone.get_current_timezone())
            else:
                start_date = usage.start_date
            
            month = start_date.strftime('%Y-%m')
            if month not in monthly_trends:
                monthly_trends[month] = {
                    'data_usage': 0,
                    'call_minutes': 0,
                    'sms_used': 0,
                    'spent_amount': 0
                }
            monthly_trends[month]['data_usage'] += usage.data_usage or 0
            monthly_trends[month]['call_minutes'] += usage.call_minutes or 0
            monthly_trends[month]['sms_used'] += usage.sms_used or 0
            monthly_trends[month]['spent_amount'] += usage.spent_amount or 0

        # So sánh 3 tháng gần đây với 3 tháng trước đó
        recent_stats = ServiceUsage.objects.filter(
            user=user,
            start_date__gte=three_months_ago
        ).aggregate(
            data_usage=Coalesce(Sum('data_usage', output_field=FloatField()), 0.0),
            call_minutes=Coalesce(Sum('call_minutes', output_field=FloatField()), 0.0),
            sms_used=Coalesce(Sum('sms_used', output_field=FloatField()), 0.0),
            spent_amount=Coalesce(Sum('spent_amount', output_field=FloatField()), 0.0)
        )

        previous_stats = ServiceUsage.objects.filter(
            user=user,
            start_date__gte=six_months_ago,
            start_date__lt=three_months_ago
        ).aggregate(
            data_usage=Coalesce(Sum('data_usage', output_field=FloatField()), 0.0),
            call_minutes=Coalesce(Sum('call_minutes', output_field=FloatField()), 0.0),
            sms_used=Coalesce(Sum('sms_used', output_field=FloatField()), 0.0),
            spent_amount=Coalesce(Sum('spent_amount', output_field=FloatField()), 0.0)
        )

        # Tính phần trăm thay đổi
        changes = {}
        for key in ['data_usage', 'call_minutes', 'sms_used', 'spent_amount']:
            if previous_stats[key] > 0:
                change = ((recent_stats[key] - previous_stats[key]) / previous_stats[key]) * 100
                changes[key] = round(change, 1)
            else:
                changes[key] = 0

        return {
            'monthly_trends': monthly_trends,
            'recent_vs_previous': changes
        }

    def _analyze_churn_factors(self, customer, feature_importance):
        """Phân tích chi tiết các yếu tố ảnh hưởng đến churn"""
        churn_factors = []
        for feature, importance in feature_importance.items():
            if importance > 0.05:  # Chỉ xem xét các yếu tố có tầm quan trọng > 5%
                factor = {
                    'name': feature.replace('_', ' ').title(),
                    'importance': importance,
                    'value': customer.get(feature, 0),
                    'impact': 'high' if importance > 0.15 else 'medium' if importance > 0.1 else 'low'
                }
                
                # Thêm mô tả và đề xuất cải thiện
                if feature == 'months_since_joined':
                    factor['description'] = f"Customer has been with us for {customer.get('months_since_joined', 0):.1f} months"
                    factor['suggestion'] = "Consider offering loyalty rewards or special promotions for long-term customers"
                elif feature == 'num_service_plans':
                    factor['description'] = f"Customer has used {customer.get('total_packages', 0)} service plans"
                    factor['suggestion'] = "Recommend new service plans that match their usage patterns"
                elif feature == 'total_spent':
                    factor['description'] = f"Customer has spent {customer.get('total_spent', 0):,.0f} VND"
                    factor['suggestion'] = "Offer personalized discounts based on spending history"
                elif feature == 'avg_rating':
                    factor['description'] = f"Customer's average support rating is {customer.get('avg_rating', 0):.1f}/5.0"
                    if customer.get('avg_rating', 0) < 4.0:
                        factor['suggestion'] = "Improve support experience and follow up on low-rated interactions"
                    else:
                        factor['suggestion'] = "Maintain high quality support and consider for referral program"
                elif feature == 'total_savings':
                    factor['description'] = f"Customer has saved {customer.get('total_savings', 0):,.0f} VND through promotions"
                    factor['suggestion'] = "Highlight potential savings in upcoming promotions"
                else:
                    factor['description'] = f"Current value: {customer.get(feature, 0)}"
                    factor['suggestion'] = "Monitor this metric for significant changes"

                churn_factors.append(factor)

        return sorted(churn_factors, key=lambda x: x['importance'], reverse=True)

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

    def prepare_data_view(self, request):
        """View for preparing and analyzing training data"""
        if not request.user.is_superuser:
            return JsonResponse({
                'status': 'error',
                'message': 'Only superusers can access this functionality'
            }, status=403)

        try:
            data = json.loads(request.body)
            reference_date = data.get('reference_date')
            
            # Convert reference_date string to datetime if provided
            if reference_date:
                reference_date = datetime.strptime(reference_date, '%Y-%m-%d').replace(tzinfo=pytz.UTC)
            
            # Initialize model
            model = ChurnPredictionModel()
            
            # Get data statistics
            data_stats = model.get_data_statistics(reference_date)
            
            return JsonResponse({
                'status': 'success',
                'data': data_stats
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)

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