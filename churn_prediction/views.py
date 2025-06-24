from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .ml_model import ChurnPredictionModel
import json
from datetime import datetime
import pytz

# Create your views here.

def train_model_view(request):
    """View for displaying the model training interface"""
    return render(request, 'churn_prediction/train_model.html')

@csrf_exempt
def prepare_data(request):
    """API endpoint to prepare and analyze training data"""
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

@csrf_exempt
def train_model(request):
    """API endpoint to train the model with specified parameters"""
    try:
        data = json.loads(request.body)
        reference_date = data.get('reference_date')
        smote_ratio = float(data.get('smote_ratio', 0.5))  # Default to 0.5 if not provided
        test_size = float(data.get('test_size', 0.2))      # Default to 0.2 if not provided
        
        # Convert reference_date string to datetime if provided
        if reference_date:
            reference_date = datetime.strptime(reference_date, '%Y-%m-%d').replace(tzinfo=pytz.UTC)
        
        # Initialize model
        model = ChurnPredictionModel()
        
        # Train model with specified parameters
        metrics = model.train(
            reference_date=reference_date,
            test_size=test_size,
            smote_ratio=smote_ratio
        )
        
        return JsonResponse({
            'status': 'success',
            'metrics': metrics
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)
