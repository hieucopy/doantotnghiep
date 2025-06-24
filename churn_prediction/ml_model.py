import os
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
from django.conf import settings
from sqlalchemy import create_engine
from datetime import datetime, timedelta
import pytz
from django.db import connection
from django.db.models import Model
from .models import ModelEvaluation
from imblearn.under_sampling import RandomUnderSampler
from imblearn.over_sampling import SMOTE

class ChurnPredictionModel:
    def __init__(self):
        self.model = None
        self.scaler = None
        self.model_path = os.path.join(settings.BASE_DIR, 'churn_prediction', 'ml_models', 'churn_model.joblib')
        self.scaler_path = os.path.join(settings.BASE_DIR, 'churn_prediction', 'ml_models', 'scaler.joblib')
        self.engine = create_engine('mysql+pymysql://root:hieu@localhost/my_telecom_db')
        self._load_model()

    def _load_model(self):
        """Load model và scaler đã lưu (nếu có)"""
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        try:
            if os.path.exists(self.model_path):
                self.model = joblib.load(self.model_path)
            if os.path.exists(self.scaler_path):
                self.scaler = joblib.load(self.scaler_path)
        except Exception as e:
            print(f"Error loading model: {str(e)}")
            self.model = None
            self.scaler = None

    def _save_model(self):
        """Lưu model và scaler"""
        if self.model:
            joblib.dump(self.model, self.model_path)
        if self.scaler:
            joblib.dump(self.scaler, self.scaler_path)

    def _load_and_prepare_data(self, reference_date=None):
        """Tải và chuẩn bị dữ liệu từ MySQL với nhãn churn"""
        try:
            # Đảm bảo reference_date có timezone
            if reference_date is None:
                reference_date = datetime.now(pytz.UTC)
            elif reference_date.tzinfo is None:
                reference_date = pytz.UTC.localize(reference_date)
            
            print(f"\nĐang tải dữ liệu với ngày tham chiếu: {reference_date}")
            
            # Query để lấy dữ liệu người dùng với các tính năng mới
            query = """
                SELECT 
                    u.id as user_id,
                    u.username,
                    u.date_joined,
                    u.last_login,
                    TIMESTAMPDIFF(MONTH, u.date_joined, %s) as months_since_joined,
                    TIMESTAMPDIFF(DAY, u.last_login, %s) as days_since_last_login,
                    COUNT(DISTINCT su.id) as num_service_plans,
                    COALESCE(SUM(su.spent_amount), 0) as total_spent,
                    COALESCE(AVG(su.spent_amount), 0) as avg_spent_per_plan,
                    COALESCE(SUM(su.data_usage), 0) as total_data_usage,
                    COALESCE(AVG(su.data_usage), 0) as avg_data_usage,
                    COALESCE(SUM(su.call_minutes), 0) as total_call_minutes,
                    COALESCE(AVG(su.call_minutes), 0) as avg_call_minutes,
                    COALESCE(SUM(su.sms_used), 0) as total_sms_used,
                    COALESCE(AVG(su.sms_used), 0) as avg_sms_used,
                    COUNT(DISTINCT st.id) as num_support_tickets,
                    COALESCE(AVG(st.rating), 0) as avg_rating,
                    COALESCE(SUM(su.spent_amount), 0) as total_savings,
                    -- Tính toán các metrics trong 3 tháng gần đây
                    SUM(CASE WHEN su.start_date >= DATE_SUB(%s, INTERVAL 3 MONTH) THEN su.spent_amount ELSE 0 END) as recent_spent,
                    SUM(CASE WHEN su.start_date >= DATE_SUB(%s, INTERVAL 3 MONTH) THEN su.data_usage ELSE 0 END) as recent_data_usage,
                    SUM(CASE WHEN su.start_date >= DATE_SUB(%s, INTERVAL 3 MONTH) THEN su.call_minutes ELSE 0 END) as recent_call_minutes,
                    SUM(CASE WHEN su.start_date >= DATE_SUB(%s, INTERVAL 3 MONTH) THEN su.sms_used ELSE 0 END) as recent_sms_used,
                    COUNT(DISTINCT CASE WHEN su.start_date >= DATE_SUB(%s, INTERVAL 3 MONTH) THEN su.id END) as recent_service_plans,
                    -- Tính toán tỷ lệ sử dụng dịch vụ
                    CASE 
                        WHEN COUNT(DISTINCT su.id) > 0 THEN 
                            COUNT(DISTINCT CASE WHEN su.start_date >= DATE_SUB(%s, INTERVAL 3 MONTH) THEN su.id END) * 100.0 / COUNT(DISTINCT su.id)
                        ELSE 0 
                    END as service_usage_ratio,
                    -- Tính toán tần suất sử dụng dịch vụ
                    CASE 
                        WHEN TIMESTAMPDIFF(MONTH, u.date_joined, %s) > 0 THEN 
                            COUNT(DISTINCT su.id) * 1.0 / TIMESTAMPDIFF(MONTH, u.date_joined, %s)
                        ELSE 0 
                    END as service_frequency,
                    -- Nhãn churn: người dùng được coi là churn nếu:
                    -- 1. Không đăng nhập trong 90 ngày trước ngày tham chiếu
                    -- 2. Hoặc có hoạt động giảm đáng kể trong 3 tháng gần nhất
                    CASE 
                        WHEN (
                            u.last_login < DATE_SUB(%s, INTERVAL 90 DAY) OR
                            (
                                COUNT(DISTINCT CASE WHEN su.start_date >= DATE_SUB(%s, INTERVAL 3 MONTH) THEN su.id END) * 1.0 /
                                NULLIF(COUNT(DISTINCT CASE WHEN su.start_date >= DATE_SUB(%s, INTERVAL 6 MONTH) 
                                    AND su.start_date < DATE_SUB(%s, INTERVAL 3 MONTH) THEN su.id END), 0) < 0.5
                            )
                        ) THEN 1
                        ELSE 0
                    END as churned
                FROM users_customuser u
                LEFT JOIN services_serviceusage su ON u.id = su.user_id
                LEFT JOIN support_supportticket st ON u.id = st.user_id
                WHERE u.date_joined <= %s
                GROUP BY u.id, u.username, u.date_joined, u.last_login
                HAVING COUNT(DISTINCT su.id) > 0
            """
            
            # Đếm số lượng %s trong query (19 tham số)
            # Thực hiện query với reference_date
            features = pd.read_sql(
                query, 
                self.engine, 
                params=(
                    reference_date,  # months_since_joined
                    reference_date,  # days_since_last_login
                    reference_date,  # recent_spent
                    reference_date,  # recent_data_usage
                    reference_date,  # recent_call_minutes
                    reference_date,  # recent_sms_used
                    reference_date,  # recent_service_plans
                    reference_date,  # service_usage_ratio
                    reference_date,  # service_frequency (1)
                    reference_date,  # service_frequency (2)
                    reference_date,  # churn condition 1
                    reference_date,  # churn condition 2 (3 months)
                    reference_date,  # churn condition 2 (6 months)
                    reference_date,  # churn condition 2 (3 months comparison)
                    reference_date,  # WHERE clause
                )
            )
            
            if features.empty:
                raise ValueError("Không có dữ liệu để huấn luyện model")
            
            # In thông tin về phân phối dữ liệu
            print("\nThông tin về dữ liệu:")
            print(f"Tổng số mẫu: {len(features)}")
            print(f"Số mẫu churn (1): {features['churned'].sum()}")
            print(f"Số mẫu không churn (0): {len(features) - features['churned'].sum()}")
            print(f"Tỷ lệ churn: {features['churned'].mean():.2%}")
            
            # Kiểm tra phân phối thời gian
            print("\nPhân phối thời gian:")
            print(f"Ngày tham chiếu: {reference_date}")
            print(f"Khoảng thời gian dữ liệu: từ {features['date_joined'].min()} đến {features['last_login'].max()}")
            
            # Chuyển đổi datetime columns sang timezone-aware
            for col in ['date_joined', 'last_login']:
                if col in features.columns:
                    features[col] = pd.to_datetime(features[col], utc=True)
            
            # Xử lý dữ liệu
            numeric_columns = [
                'months_since_joined', 'days_since_last_login',
                'num_service_plans', 'total_spent', 'avg_spent_per_plan',
                'total_data_usage', 'avg_data_usage',
                'total_call_minutes', 'avg_call_minutes',
                'total_sms_used', 'avg_sms_used',
                'num_support_tickets', 'avg_rating', 'total_savings',
                'recent_spent', 'recent_data_usage', 'recent_call_minutes',
                'recent_sms_used', 'recent_service_plans',
                'service_usage_ratio', 'service_frequency'
            ]
            
            # Xử lý các cột số
            for col in numeric_columns:
                if col in features.columns:
                    features[col] = pd.to_numeric(features[col], errors='coerce')
                    # Thay thế giá trị NaN bằng 0
                    features[col] = features[col].fillna(0)
                    # Xử lý outliers bằng cách giới hạn trong khoảng 3 standard deviations
                    mean = features[col].mean()
                    std = features[col].std()
                    features[col] = features[col].clip(lower=mean - 3*std, upper=mean + 3*std)
            
            # Thêm các tính năng tương tác
            features['spent_per_month'] = features['total_spent'] / features['months_since_joined'].replace(0, 1)
            features['data_per_month'] = features['total_data_usage'] / features['months_since_joined'].replace(0, 1)
            features['calls_per_month'] = features['total_call_minutes'] / features['months_since_joined'].replace(0, 1)
            features['sms_per_month'] = features['total_sms_used'] / features['months_since_joined'].replace(0, 1)
            
            # Tính toán tỷ lệ sử dụng dịch vụ gần đây
            features['recent_usage_ratio'] = features['recent_service_plans'] / features['num_service_plans'].replace(0, 1)
            
            # Lưu thông tin về ngày tham chiếu vào file CSV
            csv_path = os.path.join(settings.BASE_DIR, 'churn_prediction', 'data', 'training_data.csv')
            os.makedirs(os.path.dirname(csv_path), exist_ok=True)
            
            # Tạo DataFrame để lưu với thứ tự cột mong muốn
            columns_to_save = [
                'user_id', 'username', 'date_joined', 'last_login',
                'months_since_joined', 'days_since_last_login',
                'num_service_plans', 'total_spent', 'avg_spent_per_plan',
                'total_data_usage', 'avg_data_usage',
                'total_call_minutes', 'avg_call_minutes',
                'total_sms_used', 'avg_sms_used',
                'num_support_tickets', 'avg_rating', 'total_savings',
                'recent_spent', 'recent_data_usage', 'recent_call_minutes',
                'recent_sms_used', 'recent_service_plans',
                'service_usage_ratio', 'service_frequency',
                'spent_per_month', 'data_per_month',
                'calls_per_month', 'sms_per_month',
                'recent_usage_ratio',
                'churned'
            ]
            
            # Lưu file với timestamp và reference date
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            csv_filename = f'training_data_{timestamp}_ref_{reference_date.strftime("%Y%m%d")}.csv'
            csv_path = os.path.join(settings.BASE_DIR, 'churn_prediction', 'data', csv_filename)
            
            # Lưu file với encoding UTF-8 và index=False
            features[columns_to_save].to_csv(csv_path, index=False, encoding='utf-8')

            # Trả về DataFrame chỉ với các cột cần thiết cho training
            training_columns = [
                'months_since_joined', 'days_since_last_login',
                'num_service_plans', 'total_spent', 'avg_spent_per_plan',
                'total_data_usage', 'avg_data_usage',
                'total_call_minutes', 'avg_call_minutes',
                'total_sms_used', 'avg_sms_used',
                'num_support_tickets', 'avg_rating', 'total_savings',
                'recent_spent', 'recent_data_usage', 'recent_call_minutes',
                'recent_sms_used', 'recent_service_plans',
                'service_usage_ratio', 'service_frequency',
                'spent_per_month', 'data_per_month',
                'calls_per_month', 'sms_per_month',
                'recent_usage_ratio'
            ]
            return features[training_columns + ['user_id', 'churned']]

        except Exception as e:
            raise ValueError(f"Lỗi khi chuẩn bị dữ liệu: {str(e)}")

    def train(self, reference_date=None, test_size=0.2, smote_ratio=0.5, **rf_params):
        """Huấn luyện model với dữ liệu từ MySQL
        
        Args:
            reference_date: Ngày tham chiếu để xác định churn
            test_size: Tỷ lệ dữ liệu test (mặc định 0.2)
            smote_ratio: Tỷ lệ mẫu churn so với mẫu không churn sau khi áp dụng SMOTE (mặc định 0.5)
            **rf_params: Các tham số tùy chỉnh cho RandomForestClassifier
        """
        df = self._load_and_prepare_data(reference_date)
        if df.empty:
            raise ValueError("Không có đủ dữ liệu để huấn luyện model")
        
        X = df.drop(columns=['user_id', 'churned'])
        y = df['churned'].astype(int)
        
        # Kiểm tra cân bằng dữ liệu
        class_counts = y.value_counts()
        if len(class_counts) < 2:
            raise ValueError("Dữ liệu chỉ có một lớp, không thể huấn luyện model")
        
        print(f"Phân phối lớp ban đầu: {class_counts.to_dict()}")
        
        # Tính số lượng mẫu cần tạo dựa trên smote_ratio
        target_samples = int(class_counts[0] * smote_ratio)
        if target_samples > class_counts[1]:
            print(f"Áp dụng SMOTE với tỷ lệ {smote_ratio}...")
            smote = SMOTE(random_state=42, sampling_strategy={1: target_samples})
            X_resampled, y_resampled = smote.fit_resample(X, y)
            print(f"Phân phối lớp sau khi oversampling: {pd.Series(y_resampled).value_counts().to_dict()}")
            X = X_resampled
            y = y_resampled
        
        # Chia dữ liệu thành tập train và test với stratification
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42, stratify=y
        )
        
        # Chuẩn hóa dữ liệu
        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Thiết lập các tham số mặc định nếu không được cung cấp
        default_params = {
            'n_estimators': 200,
            'max_depth': None,  # Không giới hạn độ sâu
            'min_samples_split': 2,
            'min_samples_leaf': 1,
            'max_features': 'sqrt',
            'class_weight': 'balanced',
            'random_state': 42,
            'n_jobs': -1,
            'bootstrap': True,
            'oob_score': True
        }
        
        # Cập nhật các tham số mặc định với các tham số được cung cấp
        rf_params = {**default_params, **rf_params}
        
        print("\nCác tham số RandomForest được sử dụng:")
        for param, value in rf_params.items():
            print(f"{param}: {value}")
        
        # Huấn luyện model với các tham số đã cấu hình
        self.model = RandomForestClassifier(**rf_params)
        
        # Huấn luyện model
        self.model.fit(X_train_scaled, y_train)
        
        # Đánh giá model
        y_pred = self.model.predict(X_test_scaled)
        y_pred_proba = self.model.predict_proba(X_test_scaled)[:, 1]
        
        # Tính toán các metrics
        metrics = {
            'accuracy': accuracy_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred, zero_division=0),
            'recall': recall_score(y_test, y_pred, zero_division=0),
            'f1_score': f1_score(y_test, y_pred, zero_division=0),
            'reference_date': reference_date.strftime('%Y-%m-%d') if reference_date else None,
            'train_size': len(X_train),
            'test_size': len(X_test),
            'oob_score': self.model.oob_score_ if hasattr(self.model, 'oob_score_') else None,
            'model_params': rf_params
        }
        
        # Chỉ tính ROC AUC nếu có đủ samples cho cả hai lớp
        if len(np.unique(y_test)) > 1:
            metrics['roc_auc'] = roc_auc_score(y_test, y_pred_proba)
        else:
            metrics['roc_auc'] = None
            print("Cảnh báo: Không thể tính ROC AUC vì chỉ có một lớp trong tập test")
        
        # In thông tin chi tiết về kết quả
        print("\nKết quả đánh giá model:")
        print(f"Accuracy: {metrics['accuracy']:.4f}")
        print(f"Precision: {metrics['precision']:.4f}")
        print(f"Recall: {metrics['recall']:.4f}")
        print(f"F1 Score: {metrics['f1_score']:.4f}")
        if metrics['roc_auc'] is not None:
            print(f"ROC AUC: {metrics['roc_auc']:.4f}")
        if metrics['oob_score'] is not None:
            print(f"Out-of-bag Score: {metrics['oob_score']:.4f}")
        
        # In thông tin về feature importance
        feature_importance = pd.DataFrame({
            'feature': X.columns,
            'importance': self.model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        print("\nTop 10 Feature Importance:")
        for _, row in feature_importance.head(10).iterrows():
            print(f"{row['feature']}: {row['importance']:.4f}")
        
        # Lưu model và scaler
        self._save_model()
        
        # Tự động lưu dự đoán cho tất cả người dùng tại ngày tham chiếu
        if reference_date is not None:
            try:
                saved_count = self.save_predictions(reference_date)
                print(f"\nĐã tự động lưu dự đoán cho {saved_count} người dùng tại ngày {reference_date.strftime('%d/%m/%Y')}")
            except Exception as e:
                print(f"\nLỗi khi tự động lưu dự đoán: {str(e)}")
        
        return metrics

    def predict_batch_users(self, user_ids, reference_date=None):
        """Dự đoán xác suất churn cho một batch users
        
        Args:
            user_ids: List các user_id cần dự đoán
            reference_date: Ngày tham chiếu để tính toán features
            
        Returns:
            dict: Dictionary chứa kết quả dự đoán cho mỗi user
        """
        if not self.model or not self.scaler:
            raise ValueError("Model chưa được huấn luyện")
        
        if reference_date is None:
            reference_date = pd.Timestamp.now(tz='UTC')
            
        try:
            # Query để lấy dữ liệu cho nhiều users cùng lúc
            query = """
                WITH user_metrics AS (
                SELECT 
                        u.id,
                        COALESCE(TIMESTAMPDIFF(MONTH, u.date_joined, %(ref_date)s), 0) as months_since_joined,
                        COALESCE(TIMESTAMPDIFF(DAY, u.last_login, %(ref_date)s), 0) as days_since_last_login,
                    COUNT(DISTINCT su.id) as num_service_plans,
                    COALESCE(SUM(su.spent_amount), 0) as total_spent,
                    COALESCE(AVG(su.spent_amount), 0) as avg_spent_per_plan,
                    COALESCE(SUM(su.data_usage), 0) as total_data_usage,
                    COALESCE(AVG(su.data_usage), 0) as avg_data_usage,
                    COALESCE(SUM(su.call_minutes), 0) as total_call_minutes,
                    COALESCE(AVG(su.call_minutes), 0) as avg_call_minutes,
                    COALESCE(SUM(su.sms_used), 0) as total_sms_used,
                    COALESCE(AVG(su.sms_used), 0) as avg_sms_used,
                    COUNT(DISTINCT st.id) as num_support_tickets,
                    COALESCE(AVG(st.rating), 0) as avg_rating,
                    COALESCE(SUM(su.spent_amount), 0) as total_savings,
                        COALESCE(SUM(CASE WHEN su.start_date >= DATE_SUB(%(ref_date)s, INTERVAL 3 MONTH) 
                            THEN su.spent_amount ELSE 0 END), 0) as recent_spent,
                        COALESCE(SUM(CASE WHEN su.start_date >= DATE_SUB(%(ref_date)s, INTERVAL 3 MONTH) 
                            THEN su.data_usage ELSE 0 END), 0) as recent_data_usage,
                        COALESCE(SUM(CASE WHEN su.start_date >= DATE_SUB(%(ref_date)s, INTERVAL 3 MONTH) 
                            THEN su.call_minutes ELSE 0 END), 0) as recent_call_minutes,
                        COALESCE(SUM(CASE WHEN su.start_date >= DATE_SUB(%(ref_date)s, INTERVAL 3 MONTH) 
                            THEN su.sms_used ELSE 0 END), 0) as recent_sms_used,
                        COALESCE(COUNT(DISTINCT CASE WHEN su.start_date >= DATE_SUB(%(ref_date)s, INTERVAL 3 MONTH) 
                            THEN su.id END), 0) as recent_service_plans,
                    CASE 
                        WHEN COUNT(DISTINCT su.id) > 0 THEN 
                                COALESCE(COUNT(DISTINCT CASE WHEN su.start_date >= DATE_SUB(%(ref_date)s, INTERVAL 3 MONTH) 
                                    THEN su.id END) * 100.0 / NULLIF(COUNT(DISTINCT su.id), 0), 0)
                        ELSE 0 
                    END as service_usage_ratio,
                    CASE 
                            WHEN COALESCE(TIMESTAMPDIFF(MONTH, u.date_joined, %(ref_date)s), 0) > 0 THEN 
                                COUNT(DISTINCT su.id) * 1.0 / NULLIF(TIMESTAMPDIFF(MONTH, u.date_joined, %(ref_date)s), 0)
                        ELSE 0 
                    END as service_frequency
                FROM users_customuser u
                LEFT JOIN services_serviceusage su ON u.id = su.user_id
                LEFT JOIN support_supportticket st ON u.id = st.user_id
                    WHERE u.id IN %(user_ids)s
                    GROUP BY u.id
                )
                SELECT * FROM user_metrics
            """
            
            # Thực hiện query với các tham số
            params = {
                'ref_date': reference_date,
                'user_ids': tuple(user_ids)
            }
            df = pd.read_sql(query, self.engine, params=params)
            
            if df.empty:
                raise ValueError(f"Không tìm thấy dữ liệu cho users")
            
            # Đảm bảo không có giá trị null
            df = df.fillna(0)
            
            # Tính toán các features phụ thuộc
            months_since_joined = df['months_since_joined'].replace(0, 1)  # Tránh chia cho 0
            df['spent_per_month'] = df['total_spent'] / months_since_joined
            df['data_per_month'] = df['total_data_usage'] / months_since_joined
            df['calls_per_month'] = df['total_call_minutes'] / months_since_joined
            df['sms_per_month'] = df['total_sms_used'] / months_since_joined
            df['recent_usage_ratio'] = df['recent_service_plans'] / df['num_service_plans'].replace(0, 1)
            
            # Đảm bảo thứ tự và tên các features giống như khi training
            feature_columns = [
                'months_since_joined', 'days_since_last_login',
                'num_service_plans', 'total_spent', 'avg_spent_per_plan',
                'total_data_usage', 'avg_data_usage',
                'total_call_minutes', 'avg_call_minutes',
                'total_sms_used', 'avg_sms_used',
                'num_support_tickets', 'avg_rating', 'total_savings',
                'recent_spent', 'recent_data_usage', 'recent_call_minutes',
                'recent_sms_used', 'recent_service_plans',
                'service_usage_ratio', 'service_frequency',
                'spent_per_month', 'data_per_month',
                'calls_per_month', 'sms_per_month',
                'recent_usage_ratio'
            ]
            
            # Chỉ lấy các features cần thiết theo đúng thứ tự
            features = df[feature_columns]
            
            # Chuẩn hóa features
            features_scaled = self.scaler.transform(features)
            
            # Dự đoán xác suất churn cho tất cả users
            churn_probabilities = self.model.predict_proba(features_scaled)[:, 1]
            
            # Xác định các yếu tố chính ảnh hưởng đến dự đoán
            feature_importance = pd.DataFrame({
                'feature': feature_columns,
                'importance': self.model.feature_importances_
            }).sort_values('importance', ascending=False)
            
            # Tạo kết quả cho từng user
            results = {}
            for i, user_id in enumerate(df['id']):
                churn_probability = float(churn_probabilities[i])
                risk_level = "Cao" if churn_probability >= 0.7 else "Trung bình" if churn_probability >= 0.3 else "Thấp"
                
                results[user_id] = {
                    'user_id': int(user_id),
                    'prediction_date': reference_date,
                    'churn_probability': churn_probability,
                    'risk_level': risk_level,
                    'top_factors': feature_importance.head(5).to_dict('records'),
                    'user_metrics': {
                        'months_since_joined': int(df.loc[df['id'] == user_id, 'months_since_joined'].fillna(0).iloc[0]),
                        'days_since_last_login': int(df.loc[df['id'] == user_id, 'days_since_last_login'].fillna(0).iloc[0]),
                        'total_spent': float(df.loc[df['id'] == user_id, 'total_spent'].fillna(0).iloc[0]),
                        'avg_rating': float(df.loc[df['id'] == user_id, 'avg_rating'].fillna(0).iloc[0]),
                        'recent_activity': {
                            'spent': float(df.loc[df['id'] == user_id, 'recent_spent'].fillna(0).iloc[0]),
                            'data_usage': float(df.loc[df['id'] == user_id, 'recent_data_usage'].fillna(0).iloc[0]),
                            'call_minutes': float(df.loc[df['id'] == user_id, 'recent_call_minutes'].fillna(0).iloc[0]),
                            'sms_used': int(df.loc[df['id'] == user_id, 'recent_sms_used'].fillna(0).iloc[0])
                        }
                    }
                }
            
            return results
            
        except Exception as e:
            raise ValueError(f"Lỗi khi dự đoán churn cho batch users: {str(e)}")
            
    def predict_user_churn(self, user_id, reference_date=None):
        """Dự đoán xác suất churn cho một user
        
        Args:
            user_id: ID của user cần dự đoán
            reference_date: Ngày tham chiếu để tính toán features
            
        Returns:
            dict: Dictionary chứa kết quả dự đoán
        """
        results = self.predict_batch_users([user_id], reference_date)
        return results[user_id]

    def get_feature_importance(self):
        """Lấy feature importance từ model đã huấn luyện"""
        if not self.model:
            raise ValueError("Model chưa được huấn luyện")
        
        # Lấy feature names từ dữ liệu training
        df = self._load_and_prepare_data()
        if df.empty:
            raise ValueError("Không có dữ liệu training")
        
        feature_names = df.drop(columns=['user_id', 'churned']).columns
        feature_importance = dict(zip(feature_names, self.model.feature_importances_))
        
        # Sắp xếp theo tầm quan trọng giảm dần
        return dict(sorted(feature_importance.items(), key=lambda x: x[1], reverse=True))

    def _load_unlabeled_data(self, reference_date):
        """Tải dữ liệu người dùng có hoạt động sau ngày tham chiếu (không gán nhãn)"""
        try:
            print(f"\nBắt đầu tải dữ liệu kiểm thử (unlabeled) với ngày tham chiếu: {reference_date}")
            query = '''
                SELECT DISTINCT u.id as user_id, u.username, u.date_joined, u.last_login,
                    TIMESTAMPDIFF(MONTH, u.date_joined, %s) as months_since_joined,
                    COALESCE(SUM(su.spent_amount), 0) as total_spent,
                    COALESCE(SUM(su.data_usage), 0) as total_data_usage,
                    COALESCE(SUM(su.call_minutes), 0) as total_call_minutes,
                    COALESCE(SUM(su.sms_used), 0) as total_sms_used,
                    COUNT(DISTINCT su.id) as num_service_plans,
                    COUNT(DISTINCT st.id) as num_support_tickets,
                    COALESCE(AVG(st.rating), 0) as avg_rating,
                    COALESCE(SUM(su.spent_amount), 0) as total_savings
                FROM users_customuser u
                LEFT JOIN services_serviceusage su ON u.id = su.user_id
                LEFT JOIN support_supportticket st ON u.id = st.user_id
                WHERE su.start_date > %s
                GROUP BY u.id, u.username, u.date_joined, u.last_login
                HAVING COUNT(DISTINCT su.id) > 0
            '''
            features = pd.read_sql(query, self.engine, params=(reference_date, reference_date))
            if len(features) == 0:
                print("Không có dữ liệu kiểm thử sau ngày tham chiếu.")
                return pd.DataFrame()
            # Xử lý dữ liệu giống như khi train
            features['months_since_joined'] = features['months_since_joined'].fillna(0).astype(int)
            features['num_service_plans'] = features['num_service_plans'].fillna(0).astype(int)
            features['total_spent'] = features['total_spent'].fillna(0).astype(float)
            features['total_data_usage'] = features['total_data_usage'].fillna(0).astype(float)
            features['total_call_minutes'] = features['total_call_minutes'].fillna(0).astype(float)
            features['total_sms_used'] = features['total_sms_used'].fillna(0).astype(int)
            features['num_support_tickets'] = features['num_support_tickets'].fillna(0).astype(int)
            features['avg_rating'] = features['avg_rating'].fillna(0).astype(float)
            features['total_savings'] = features['total_savings'].fillna(0).astype(float)
            return features
        except Exception as e:
            print(f"Lỗi khi tải dữ liệu kiểm thử: {e}")
            import traceback
            print("Traceback:", traceback.format_exc())
            return pd.DataFrame()

    def test_on_unlabeled(self, reference_date):
        """Kiểm thử mô hình trên dữ liệu sau ngày tham chiếu (không gán nhãn)"""
        df = self._load_unlabeled_data(reference_date)
        if df.empty:
            print("Không có dữ liệu kiểm thử để dự đoán.")
            return []
        feature_columns = [
            'months_since_joined', 'num_service_plans', 'total_spent',
            'total_data_usage', 'total_call_minutes', 'total_sms_used',
            'num_support_tickets', 'avg_rating', 'total_savings'
        ]
        X = df[feature_columns]
        X_scaled = self.scaler.transform(X)
        churn_probs = self.model.predict_proba(X_scaled)[:, 1]
        results = []
        for idx, row in df.iterrows():
            results.append({
                'user_id': row['user_id'],
                'username': row['username'],
                'churn_probability': float(churn_probs[idx]),
                'test_date': datetime.now(pytz.UTC)
            })
        print(f"Đã dự đoán xác suất churn cho {len(results)} user sau ngày tham chiếu {reference_date}.")
        return results

    def save_predictions(self, reference_date):
        """Lưu kết quả dự đoán churn tại thời điểm reference_date vào bảng ChurnPrediction"""
        try:
            # Đảm bảo reference_date có timezone
            if reference_date.tzinfo is None:
                reference_date = pytz.UTC.localize(reference_date)
            
            # Query để lấy dữ liệu với tất cả các feature cần thiết
            query = """
                SELECT 
                    u.id as user_id,
                    TIMESTAMPDIFF(MONTH, u.date_joined, %s) as months_since_joined,
                    TIMESTAMPDIFF(DAY, u.last_login, %s) as days_since_last_login,
                    COUNT(DISTINCT su.id) as num_service_plans,
                    COALESCE(SUM(su.spent_amount), 0) as total_spent,
                    COALESCE(AVG(su.spent_amount), 0) as avg_spent_per_plan,
                    COALESCE(SUM(su.data_usage), 0) as total_data_usage,
                    COALESCE(AVG(su.data_usage), 0) as avg_data_usage,
                    COALESCE(SUM(su.call_minutes), 0) as total_call_minutes,
                    COALESCE(AVG(su.call_minutes), 0) as avg_call_minutes,
                    COALESCE(SUM(su.sms_used), 0) as total_sms_used,
                    COALESCE(AVG(su.sms_used), 0) as avg_sms_used,
                    COUNT(DISTINCT st.id) as num_support_tickets,
                    COALESCE(AVG(st.rating), 0) as avg_rating,
                    COALESCE(SUM(su.spent_amount), 0) as total_savings,
                    -- Tính toán các metrics trong 3 tháng gần đây
                    SUM(CASE WHEN su.start_date >= DATE_SUB(%s, INTERVAL 3 MONTH) THEN su.spent_amount ELSE 0 END) as recent_spent,
                    SUM(CASE WHEN su.start_date >= DATE_SUB(%s, INTERVAL 3 MONTH) THEN su.data_usage ELSE 0 END) as recent_data_usage,
                    SUM(CASE WHEN su.start_date >= DATE_SUB(%s, INTERVAL 3 MONTH) THEN su.call_minutes ELSE 0 END) as recent_call_minutes,
                    SUM(CASE WHEN su.start_date >= DATE_SUB(%s, INTERVAL 3 MONTH) THEN su.sms_used ELSE 0 END) as recent_sms_used,
                    COUNT(DISTINCT CASE WHEN su.start_date >= DATE_SUB(%s, INTERVAL 3 MONTH) THEN su.id END) as recent_service_plans,
                    -- Tính toán tỷ lệ sử dụng dịch vụ
                    CASE 
                        WHEN COUNT(DISTINCT su.id) > 0 THEN 
                            COUNT(DISTINCT CASE WHEN su.start_date >= DATE_SUB(%s, INTERVAL 3 MONTH) THEN su.id END) * 100.0 / COUNT(DISTINCT su.id)
                        ELSE 0 
                    END as service_usage_ratio,
                    -- Tính toán tần suất sử dụng dịch vụ
                    CASE 
                        WHEN TIMESTAMPDIFF(MONTH, u.date_joined, %s) > 0 THEN 
                            COUNT(DISTINCT su.id) * 1.0 / TIMESTAMPDIFF(MONTH, u.date_joined, %s)
                        ELSE 0 
                    END as service_frequency
                FROM users_customuser u
                LEFT JOIN services_serviceusage su ON u.id = su.user_id
                LEFT JOIN support_supportticket st ON u.id = st.user_id
                WHERE u.date_joined <= %s
                GROUP BY u.id
                HAVING COUNT(DISTINCT su.id) > 0
            """
            
            # Thực hiện query với reference_date
            df = pd.read_sql(
                query, 
                self.engine, 
                params=(reference_date, reference_date, reference_date, reference_date, 
                       reference_date, reference_date, reference_date, reference_date,
                       reference_date, reference_date, reference_date)
            )
            
            if df.empty:
                raise ValueError("Không có dữ liệu để dự đoán")
            
            # Tính toán các tính năng bổ sung
            df['spent_per_month'] = df['total_spent'] / df['months_since_joined'].replace(0, 1)
            df['data_per_month'] = df['total_data_usage'] / df['months_since_joined'].replace(0, 1)
            df['calls_per_month'] = df['total_call_minutes'] / df['months_since_joined'].replace(0, 1)
            df['sms_per_month'] = df['total_sms_used'] / df['months_since_joined'].replace(0, 1)
            df['recent_usage_ratio'] = df['recent_service_plans'] / df['num_service_plans'].replace(0, 1)
            
            # Đảm bảo thứ tự cột giống như khi training
            feature_columns = [
                'months_since_joined', 'days_since_last_login',
                'num_service_plans', 'total_spent', 'avg_spent_per_plan',
                'total_data_usage', 'avg_data_usage',
                'total_call_minutes', 'avg_call_minutes',
                'total_sms_used', 'avg_sms_used',
                'num_support_tickets', 'avg_rating', 'total_savings',
                'recent_spent', 'recent_data_usage', 'recent_call_minutes',
                'recent_sms_used', 'recent_service_plans',
                'service_usage_ratio', 'service_frequency',
                'spent_per_month', 'data_per_month',
                'calls_per_month', 'sms_per_month',
                'recent_usage_ratio'
            ]
            
            # Chuẩn bị features cho dự đoán
            X = df[feature_columns]
            X_scaled = self.scaler.transform(X)
            
            # Dự đoán xác suất churn
            proba = self.model.predict_proba(X_scaled)
            if proba.shape[1] == 1:
                churn_probs = proba[:, 0]
            else:
                churn_probs = proba[:, 1]
            
            # Lưu kết quả vào database
            cursor = connection.cursor()
            
            # Xóa các dự đoán cũ cho cùng reference_date nếu có
            cursor.execute("""
                DELETE FROM churn_prediction_churnprediction 
                WHERE DATE(prediction_date) = DATE(%s)
            """, [reference_date])
            
            # Thêm các dự đoán mới
            insert_query = """
                INSERT INTO churn_prediction_churnprediction 
                (user_id, prediction_date, churn_probability)
                VALUES (%s, %s, %s)
            """
            
            inserted_count = 0
            for idx, row in df.iterrows():
                try:
                    cursor.execute(insert_query, [
                        int(row['user_id']),
                        reference_date,
                        float(churn_probs[idx])
                    ])
                    inserted_count += 1
                except Exception as e:
                    continue
            
            return inserted_count
            
        except Exception as e:
            raise ValueError(f"Lỗi khi lưu dự đoán: {str(e)}")

    def evaluate_model_accuracy(self, reference_date, evaluation_date=None):
        """Đánh giá độ chính xác của mô hình bằng cách so sánh dự đoán với thực tế"""
        try:
            if evaluation_date is None:
                evaluation_date = datetime.now(pytz.UTC)
            elif evaluation_date.tzinfo is None:
                evaluation_date = pytz.UTC.localize(evaluation_date)
                
            # Đảm bảo reference_date có timezone
            if reference_date.tzinfo is None:
                reference_date = pytz.UTC.localize(reference_date)

            # Kiểm tra xem có dữ liệu dự đoán cho ngày tham chiếu không
            check_query = "SELECT COUNT(*) as count FROM churn_prediction_churnprediction WHERE DATE(prediction_date) = DATE(%s)"
            result = pd.read_sql(check_query, self.engine, params=(reference_date,))
            prediction_count = result['count'].iloc[0]
            
            if prediction_count == 0:
                raise ValueError(f"Không tìm thấy dữ liệu dự đoán cho ngày {reference_date.strftime('%d/%m/%Y')}. "
                               f"Vui lòng huấn luyện mô hình và lưu dự đoán trước khi đánh giá.")

            # Query cơ bản để lấy dữ liệu
            base_query = """
                SELECT 
                    cp.user_id,
                    cp.churn_probability,
                    CONVERT_TZ(u.last_login, 'SYSTEM', 'UTC') as last_login,
                    (
                        SELECT COUNT(*) 
                        FROM services_serviceusage su 
                        WHERE su.user_id = cp.user_id 
                        AND su.start_date >= DATE_SUB(%s, INTERVAL 3 MONTH)
                        AND su.start_date < %s
                    ) as recent_activity_count,
                    (
                        SELECT COUNT(*) 
                        FROM services_serviceusage su 
                        WHERE su.user_id = cp.user_id 
                        AND su.start_date >= DATE_SUB(%s, INTERVAL 6 MONTH)
                        AND su.start_date < DATE_SUB(%s, INTERVAL 3 MONTH)
                    ) as previous_activity_count,
                    CASE WHEN EXISTS (
                        SELECT 1 FROM services_serviceusage su 
                        WHERE su.user_id = cp.user_id 
                        AND su.start_date >= %s
                        AND su.start_date < DATE_ADD(%s, INTERVAL 3 MONTH)
                    ) THEN 1 ELSE 0 END as has_service_after,
                    CASE WHEN EXISTS (
                        SELECT 1 FROM support_supportticket st 
                        WHERE st.user_id = cp.user_id 
                        AND st.created_at >= %s
                        AND st.created_at < DATE_ADD(%s, INTERVAL 3 MONTH)
                    ) THEN 1 ELSE 0 END as has_support_after
                FROM churn_prediction_churnprediction cp
                JOIN users_customuser u ON cp.user_id = u.id
                WHERE DATE(cp.prediction_date) = DATE(%s)
            """

            # Thực hiện query cơ bản
            df = pd.read_sql(base_query, self.engine, params=(
                reference_date, reference_date,  # recent_activity_count
                reference_date, reference_date,  # previous_activity_count
                reference_date, reference_date,  # has_service_after
                reference_date, reference_date,  # has_support_after
                reference_date   # WHERE clause
            ))

            if df.empty:
                raise ValueError(f"Không tìm thấy dữ liệu dự đoán cho ngày {reference_date.strftime('%d/%m/%Y')}")

            # Chuyển đổi last_login thành timezone-aware
            df['last_login'] = pd.to_datetime(df['last_login'], utc=True)
            
            # Tính toán actual_churn trong Python
            df['had_activity_after'] = (df['has_service_after'] | df['has_support_after']).astype(int)
            df['activity_ratio'] = df['recent_activity_count'] / df['previous_activity_count'].replace(0, 1)
            
            # Đảm bảo reference_date là timezone-aware khi so sánh
            inactive_threshold = reference_date - pd.Timedelta(days=90)
            df['is_inactive'] = (df['last_login'] < inactive_threshold).astype(int)
            df['has_decreased_activity'] = ((df['previous_activity_count'] > 0) & (df['activity_ratio'] < 0.5)).astype(int)
            
            # Xác định actual_churn
            df['actual_churn'] = (
                ((df['is_inactive'] == 1) | (df['has_decreased_activity'] == 1)) & 
                (df['had_activity_after'] == 0)
            ).astype(int)
            
            # Tính toán các metrics
            y_true = df['actual_churn']
            y_pred = (df['churn_probability'] >= 0.8).astype(int)
            
            # Metrics cơ bản để lưu vào database
            db_metrics = {
                'accuracy': accuracy_score(y_true, y_pred),
                'total_users': len(df),
                'actual_churns': int(y_true.sum()),
                'predicted_churns': int(y_pred.sum())
            }
            
            # Chỉ tính precision và recall nếu có cả hai lớp
            if len(y_true.unique()) > 1:
                db_metrics.update({
                    'precision': precision_score(y_true, y_pred, zero_division=0),
                    'recall': recall_score(y_true, y_pred, zero_division=0),
                    'f1_score': f1_score(y_true, y_pred, zero_division=0),
                    'roc_auc': roc_auc_score(y_true, df['churn_probability'])
                })
            else:
                db_metrics.update({
                    'precision': 0.0,
                    'recall': 0.0,
                    'f1_score': 0.0,
                    'roc_auc': 0.0
                })
            
            # Lưu kết quả đánh giá vào database
            ModelEvaluation.objects.create(
                reference_date=reference_date,
                evaluation_date=evaluation_date,
                **db_metrics
            )
            
            # Thêm thông tin bổ sung vào metrics trả về
            metrics = db_metrics.copy()
            metrics.update({
                'inactive_users': int(df['is_inactive'].sum()),
                'decreased_activity_users': int(df['has_decreased_activity'].sum()),
                'had_activity_after': int(df['had_activity_after'].sum())
            })
            
            return metrics

        except Exception as e:
            raise ValueError(f"Lỗi khi đánh giá mô hình: {str(e)}")

    def get_data_statistics(self, reference_date=None):
        """Phân tích dữ liệu trước khi huấn luyện
        
        Args:
            reference_date: Ngày tham chiếu để xác định churn
            
        Returns:
            dict: Dictionary chứa các thống kê về dữ liệu
        """
        df = self._load_and_prepare_data(reference_date)
        if df.empty:
            raise ValueError("Không có đủ dữ liệu để phân tích")
        
        X = df.drop(columns=['user_id', 'churned'])
        y = df['churned'].astype(int)
        
        # Thống kê cơ bản về phân phối lớp
        class_counts = y.value_counts()
        total_samples = int(len(y))  # Convert to Python int
        
        # Convert class_counts to Python dict with int values
        class_distribution = {str(k): int(v) for k, v in class_counts.items()}
        
        # Tính toán tỷ lệ mất cân bằng
        imbalance_ratio = float(class_counts.get(0, 0) / class_counts.get(1, 1)) if class_counts.get(1, 0) > 0 else float('inf')
        
        # Thống kê về features
        feature_stats = {}
        for column in X.columns:
            stats = X[column].describe()
            feature_stats[column] = {
                'mean': float(stats['mean']),
                'std': float(stats['std']),
                'min': float(stats['min']),
                'max': float(stats['max']),
                'missing': int(X[column].isnull().sum())
            }
        
        # Tính toán số lượng mẫu synthetic cần tạo với các tỷ lệ SMOTE khác nhau
        smote_scenarios = {}
        for ratio in [0.3, 0.5, 0.7, 1.0]:
            target_samples = int(class_counts.get(0, 0) * ratio)
            synthetic_samples = target_samples - int(class_counts.get(1, 0))
            if synthetic_samples < 0:
                synthetic_samples = 0
            smote_scenarios[str(ratio)] = {
                'target_samples': target_samples,
                'synthetic_samples': synthetic_samples,
                'final_ratio': float((class_counts.get(1, 0) + synthetic_samples) / class_counts.get(0, 0))
            }
        
        return {
            'total_samples': total_samples,
            'class_distribution': class_distribution,
            'imbalance_ratio': imbalance_ratio,
            'feature_statistics': feature_stats,
            'smote_scenarios': smote_scenarios,
            'reference_date': reference_date.strftime('%Y-%m-%d') if reference_date else None
        }