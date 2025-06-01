// Churn Prediction JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Khởi tạo các biểu đồ
    initializeCharts();
    
    // Xử lý sự kiện cho các nút hành động
    setupActionButtons();
    
    // Xử lý sự kiện cho form dự đoán
    setupPredictionForm();
    
    // Xử lý sự kiện cho form huấn luyện
    setupTrainingForm();
});

function initializeCharts() {
    // Khởi tạo biểu đồ phân bố xác suất rời bỏ
    const distributionCtx = document.getElementById('churnDistributionChart');
    if (distributionCtx) {
        new Chart(distributionCtx, {
            type: 'bar',
            data: {
                labels: ['0-20%', '20-40%', '40-60%', '60-80%', '80-100%'],
                datasets: [{
                    label: 'Số lượng khách hàng',
                    data: [0, 0, 0, 0, 0], // Sẽ được cập nhật từ API
                    backgroundColor: [
                        '#28a745',
                        '#5cb85c',
                        '#ffc107',
                        '#f0ad4e',
                        '#dc3545'
                    ]
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    }
    
    // Khởi tạo biểu đồ xu hướng
    const trendCtx = document.getElementById('churnTrendChart');
    if (trendCtx) {
        new Chart(trendCtx, {
            type: 'line',
            data: {
                labels: [], // Sẽ được cập nhật từ API
                datasets: [{
                    label: 'Tỷ lệ rời bỏ',
                    data: [], // Sẽ được cập nhật từ API
                    borderColor: '#dc3545',
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 1,
                        ticks: {
                            callback: function(value) {
                                return (value * 100).toFixed(0) + '%';
                            }
                        }
                    }
                }
            }
        });
    }
    
    // Khởi tạo biểu đồ tầm quan trọng của các yếu tố
    const importanceCtx = document.getElementById('featureImportanceChart');
    if (importanceCtx) {
        new Chart(importanceCtx, {
            type: 'horizontalBar',
            data: {
                labels: [], // Sẽ được cập nhật từ API
                datasets: [{
                    label: 'Tầm quan trọng',
                    data: [], // Sẽ được cập nhật từ API
                    backgroundColor: '#dc3545'
                }]
            },
            options: {
                responsive: true,
                scales: {
                    x: {
                        beginAtZero: true,
                        max: 1
                    }
                }
            }
        });
    }
}

function setupActionButtons() {
    // Xử lý sự kiện cho các nút hành động
    const actionButtons = document.querySelectorAll('.churn-action');
    actionButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const action = this.dataset.action;
            const customerId = this.dataset.customerId;
            
            switch(action) {
                case 'predict':
                    window.location.href = `/admin/analytics/customerchurnprediction/predict/?customer=${customerId}`;
                    break;
                case 'analyze':
                    window.location.href = `/admin/analytics/customerchurnprediction/analyze/`;
                    break;
                case 'train':
                    window.location.href = `/admin/analytics/customerchurnprediction/train-model/`;
                    break;
            }
        });
    });
}

function setupPredictionForm() {
    const form = document.getElementById('predictForm');
    if (form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const formData = new FormData(form);
            const customerId = formData.get('customer');
            
            // Hiển thị loading state
            const submitButton = form.querySelector('input[type="submit"]');
            const originalText = submitButton.value;
            submitButton.value = 'Đang xử lý...';
            submitButton.disabled = true;
            
            // Gửi request dự đoán
            fetch('/admin/analytics/customerchurnprediction/predict/', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': getCookie('csrftoken')
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    window.location.href = data.redirect_url;
                } else {
                    alert(data.error || 'Có lỗi xảy ra khi thực hiện dự đoán');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Có lỗi xảy ra khi thực hiện dự đoán');
            })
            .finally(() => {
                submitButton.value = originalText;
                submitButton.disabled = false;
            });
        });
    }
}

function setupTrainingForm() {
    const form = document.getElementById('trainModelForm');
    if (form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const formData = new FormData(form);
            
            // Hiển thị progress bar
            const progress = document.getElementById('trainingProgress');
            const progressBar = document.getElementById('progressBar');
            const status = document.getElementById('trainingStatus');
            const metrics = document.getElementById('modelMetrics');
            
            progress.classList.add('active');
            metrics.classList.remove('active');
            
            // Gửi request huấn luyện
            fetch('/admin/analytics/customerchurnprediction/train-model/', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': getCookie('csrftoken')
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Cập nhật metrics
                    document.getElementById('accuracy').textContent = (data.metrics.accuracy * 100).toFixed(1) + '%';
                    document.getElementById('precision').textContent = (data.metrics.precision * 100).toFixed(1) + '%';
                    document.getElementById('recall').textContent = (data.metrics.recall * 100).toFixed(1) + '%';
                    document.getElementById('f1Score').textContent = (data.metrics.f1_score * 100).toFixed(1) + '%';
                    
                    // Hiển thị kết quả
                    status.textContent = 'Huấn luyện hoàn tất!';
                    metrics.classList.add('active');
                } else {
                    alert(data.error || 'Có lỗi xảy ra khi huấn luyện mô hình');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Có lỗi xảy ra khi huấn luyện mô hình');
            });
        });
    }
}

// Utility function để lấy CSRF token
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Hàm cập nhật dữ liệu biểu đồ
function updateCharts(data) {
    // Cập nhật biểu đồ phân bố
    const distributionChart = Chart.getChart('churnDistributionChart');
    if (distributionChart) {
        distributionChart.data.datasets[0].data = data.distribution;
        distributionChart.update();
    }
    
    // Cập nhật biểu đồ xu hướng
    const trendChart = Chart.getChart('churnTrendChart');
    if (trendChart) {
        trendChart.data.labels = data.trend.labels;
        trendChart.data.datasets[0].data = data.trend.values;
        trendChart.update();
    }
    
    // Cập nhật biểu đồ tầm quan trọng
    const importanceChart = Chart.getChart('featureImportanceChart');
    if (importanceChart) {
        importanceChart.data.labels = data.importance.features;
        importanceChart.data.datasets[0].data = data.importance.values;
        importanceChart.update();
    }
} 