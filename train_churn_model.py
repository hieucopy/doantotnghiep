import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
import joblib

# Đọc dữ liệu
data = pd.read_csv('churn_data.csv')
X = data.drop(['user_id', 'churned'], axis=1)
y = data['churned']

# Chia dữ liệu
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Huấn luyện mô hình
model = RandomForestClassifier(random_state=42)
model.fit(X_train, y_train)

# Đánh giá
y_pred = model.predict(X_test)
print("Accuracy:", accuracy_score(y_test, y_pred))
print(classification_report(y_test, y_pred))

# Lưu mô hình
joblib.dump(model, 'churn_model.pkl')
print("Mô hình đã được lưu vào churn_model.pkl")