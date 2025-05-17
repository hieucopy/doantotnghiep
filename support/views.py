from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Q
from .models import SupportTicket, FAQ

@login_required
def support_home(request):
    tickets = SupportTicket.objects.filter(user=request.user).order_by('-created_at')[:5]
    faqs = FAQ.objects.all()[:5]
    return render(request, 'support/support.html', {
        'tickets': tickets,
        'faqs': faqs,
    })

@login_required
def create_ticket(request):
    if request.method == 'POST':
        subject = request.POST.get('subject')
        description = request.POST.get('description')
        priority = request.POST.get('priority', 'MEDIUM')

        if not subject or not description:
            return JsonResponse({'status': 'error', 'message': 'Vui lòng điền đầy đủ thông tin.'}, status=400)

        ticket = SupportTicket.objects.create(
            user=request.user,
            subject=subject,
            description=description,
            priority=priority,
        )
        return JsonResponse({'status': 'success', 'message': f'Yêu cầu hỗ trợ #{ticket.id} đã được gửi thành công!'})
    return render(request, 'support/create_ticket.html')

@login_required
def ticket_list(request):
    tickets = SupportTicket.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'support/ticket_list.html', {'tickets': tickets})

@login_required
def ticket_detail(request, ticket_id):
    ticket = get_object_or_404(SupportTicket, id=ticket_id, user=request.user)
    return render(request, 'support/ticket_detail.html', {'ticket': ticket})

@login_required
@require_POST
def rate_ticket(request, ticket_id):
    ticket = get_object_or_404(SupportTicket, id=ticket_id, user=request.user)
    if ticket.status != 'RESOLVED':
        return JsonResponse({'status': 'error', 'message': 'Yêu cầu phải được giải quyết trước khi đánh giá.'}, status=400)
    if ticket.rating is not None:
        return JsonResponse({'status': 'error', 'message': 'Bạn đã đánh giá yêu cầu này rồi.'}, status=400)

    rating = request.POST.get('rating')
    try:
        rating = int(rating)
        if rating < 1 or rating > 5:
            raise ValueError
    except (ValueError, TypeError):
        return JsonResponse({'status': 'error', 'message': 'Đánh giá không hợp lệ. Vui lòng chọn từ 1 đến 5 sao.'}, status=400)

    ticket.rating = rating
    ticket.save()
    return JsonResponse({'status': 'success', 'message': 'Cảm ơn bạn đã đánh giá!'})

def faq_list(request):
    query = request.GET.get('q', '')
    faqs = FAQ.objects.all()
    if query:
        faqs = faqs.filter(Q(question__icontains=query) | Q(answer__icontains=query))
    return render(request, 'support/faq.html', {'faqs': faqs, 'query': query})