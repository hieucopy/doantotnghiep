from django.db import models
from users.models import CustomUser

class ChurnPrediction(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    churn_probability = models.FloatField()
    prediction_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Prediction for {self.user.username} ({self.churn_probability:.2%})"

    class Meta:
        db_table = 'churn_prediction_churnprediction'
        verbose_name = "Dự đoán churn"
        verbose_name_plural = "Dự đoán churn"

class ModelEvaluation(models.Model):
    """Lưu kết quả đánh giá độ chính xác của mô hình"""
    reference_date = models.DateTimeField(help_text="Ngày tham chiếu khi dự đoán")
    evaluation_date = models.DateTimeField(help_text="Ngày đánh giá độ chính xác")
    accuracy = models.FloatField(help_text="Độ chính xác")
    precision = models.FloatField(help_text="Độ chính xác dương tính")
    recall = models.FloatField(help_text="Độ bao phủ")
    f1_score = models.FloatField(help_text="F1-score")
    roc_auc = models.FloatField(help_text="ROC AUC score")
    total_users = models.IntegerField(help_text="Tổng số users được đánh giá")
    actual_churns = models.IntegerField(help_text="Số lượng churn thực tế")
    predicted_churns = models.IntegerField(help_text="Số lượng churn dự đoán")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-reference_date', '-evaluation_date']
        verbose_name = "Đánh giá mô hình"
        verbose_name_plural = "Đánh giá mô hình"

    def __str__(self):
        return f"Đánh giá mô hình {self.reference_date.strftime('%Y-%m-%d')} -> {self.evaluation_date.strftime('%Y-%m-%d')}"

    @property
    def time_elapsed_days(self):
        """Số ngày từ dự đoán đến đánh giá"""
        return (self.evaluation_date - self.reference_date).days