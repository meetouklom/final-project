from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Exists, Max, OuterRef, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from .ai import AIAnalysisError, analyze_repair_request
from .forms import RepairCommentForm, RepairRatingForm, RepairRequestForm, RepairUpdateForm
from .models import RepairComment, RepairRequest
from .notifications import notify_new_comment, notify_new_repair, notify_status_change


def _can_view_repair(user, repair):
    return repair.reported_by_id == user.pk or user.is_supervisor


def _render_request_detail(request, repair, *, comment_form=None, rating_form=None, status=200):
    return render(request, 'repairs/detail.html', {
        'repair': repair,
        'update_form': RepairUpdateForm(instance=repair, language=request.LANGUAGE_CODE),
        'comment_form': comment_form or RepairCommentForm(language=request.LANGUAGE_CODE),
        'rating_form': rating_form or RepairRatingForm(language=request.LANGUAGE_CODE),
        'comments': repair.comments.select_related('author').all(),
    }, status=status)


@login_required
def create_request(request):
    initial_data = {'location': request.user.room_number} if request.user.room_number else {}
    form = RepairRequestForm(
        request.POST or None,
        request.FILES or None,
        initial=initial_data,
        language=request.LANGUAGE_CODE,
        location_locked=not request.user.is_supervisor,
        room_number=request.user.room_number,
    )
    if request.method == 'POST' and form.is_valid():
        repair = form.save(commit=False)
        repair.reported_by = request.user
        if not request.user.is_supervisor:
            repair.location = request.user.room_number
        repair.save()
        notify_new_repair(repair)
        sent_at = timezone.localtime(timezone.now())
        if request.LANGUAGE_CODE == 'en':
            messages.success(request, f'Repair request submitted at {sent_at.strftime("%d %b %Y, %H:%M")}.')
        else:
            messages.success(request, f'ส่งเรื่องแจ้งซ่อมเรียบร้อยแล้ว เวลา {sent_at.strftime("%d %b %Y, %H:%M")}')
        return redirect('dashboard')
    return render(request, 'repairs/form.html', {'form': form, 'page_title': 'New repair request'})


@login_required
def request_detail(request, pk):
    repair = get_object_or_404(RepairRequest.objects.select_related('reported_by', 'assigned_to'), pk=pk)
    if not _can_view_repair(request.user, repair):
        raise PermissionDenied
    return _render_request_detail(request, repair)


@login_required
def comment_management(request):
    if not request.user.is_supervisor:
        raise PermissionDenied

    discussions = RepairRequest.objects.annotate(
        latest_comment_at=Max('comments__created_at'),
        comment_count=Count('comments'),
    ).filter(comment_count__gt=0)
    search = request.GET.get('q', '').strip()[:100]
    if search:
        matching_comment = RepairComment.objects.filter(
            repair_id=OuterRef('pk'),
            body__icontains=search,
        )
        discussions = discussions.filter(
            Q(title__icontains=search)
            | Q(location__icontains=search)
            | Q(reported_by__username__icontains=search)
            | Q(reported_by__first_name__icontains=search)
            | Q(reported_by__last_name__icontains=search)
            | Q(Exists(matching_comment))
        )

    discussions = discussions.select_related('reported_by').prefetch_related(
        Prefetch(
            'comments',
            queryset=RepairComment.objects.select_related('author').order_by('created_at', 'pk'),
        ),
    ).order_by('-latest_comment_at', '-pk')
    page_obj = Paginator(discussions, 15).get_page(request.GET.get('page'))
    return render(request, 'repairs/comment_management.html', {
        'page_obj': page_obj,
        'discussions': page_obj.object_list,
        'search': search,
    })


@login_required
@require_POST
def reply_from_comment_management(request, pk):
    if not request.user.is_supervisor:
        raise PermissionDenied

    repair = get_object_or_404(RepairRequest, pk=pk)
    form = RepairCommentForm(request.POST, language=request.LANGUAGE_CODE)
    if not form.is_valid():
        messages.error(
            request,
            'Your reply could not be sent. Please check that it is not empty and is under 2,000 characters.'
            if request.LANGUAGE_CODE == 'en'
            else 'ส่งคำตอบไม่สำเร็จ กรุณาตรวจสอบว่าไม่ได้เว้นว่างและมีความยาวไม่เกิน 2,000 ตัวอักษร',
        )
        return redirect('comment_management')

    comment = RepairComment.objects.create(
        repair=repair,
        author=request.user,
        body=form.cleaned_data['body'],
    )
    notify_new_comment(repair, request.user, comment.body)
    messages.success(
        request,
        'Reply sent.'
        if request.LANGUAGE_CODE == 'en'
        else 'ส่งคำตอบเรียบร้อยแล้ว',
    )
    return redirect(f'{reverse("comment_management")}#discussion-{repair.pk}')


@login_required
def add_repair_comment(request, pk):
    repair = get_object_or_404(RepairRequest, pk=pk)
    if not _can_view_repair(request.user, repair):
        raise PermissionDenied
    if request.method != 'POST':
        return redirect('repair_detail', pk=repair.pk)

    form = RepairCommentForm(request.POST, language=request.LANGUAGE_CODE)
    if form.is_valid():
        comment = RepairComment.objects.create(
            repair=repair,
            author=request.user,
            body=form.cleaned_data['body'],
        )
        notify_new_comment(repair, request.user, comment.body)
        return redirect('repair_detail', pk=repair.pk)

    return _render_request_detail(
        request,
        repair,
        comment_form=form,
        status=400,
    )


@login_required
def rate_repair(request, pk):
    repair = get_object_or_404(RepairRequest, pk=pk)
    if repair.reported_by_id != request.user.pk:
        raise PermissionDenied
    if request.method != 'POST':
        return redirect('repair_detail', pk=repair.pk)
    if repair.status != RepairRequest.Status.COMPLETED or repair.rating is not None:
        raise PermissionDenied

    form = RepairRatingForm(request.POST, language=request.LANGUAGE_CODE)
    if form.is_valid():
        updated = RepairRequest.objects.filter(
            pk=repair.pk,
            status=RepairRequest.Status.COMPLETED,
            rating__isnull=True,
        ).update(rating=form.cleaned_data['rating'])
        if not updated:
            raise PermissionDenied
        if request.LANGUAGE_CODE == 'en':
            messages.success(request, 'Thanks for rating this repair.')
        else:
            messages.success(request, 'ขอบคุณสำหรับการให้คะแนนงานซ่อม')
        return redirect('repair_detail', pk=repair.pk)

    return _render_request_detail(
        request,
        repair,
        rating_form=form,
        status=400,
    )


@login_required
def update_request(request, pk):
    if not request.user.is_supervisor:
        raise PermissionDenied
    repair = get_object_or_404(RepairRequest, pk=pk)
    previous_status = repair.status
    form = RepairUpdateForm(request.POST or None, instance=repair, language=request.LANGUAGE_CODE)
    if request.method == 'POST' and form.is_valid():
        repair = form.save()
        if repair.status != previous_status:
            notify_status_change(repair, previous_status)
        if request.LANGUAGE_CODE == 'en':
            messages.success(request, 'Repair status updated.')
        else:
            messages.success(request, 'อัปเดตสถานะเรื่องแจ้งซ่อมเรียบร้อยแล้ว')
    return redirect('repair_detail', pk=repair.pk)


@login_required
@require_POST
def analyze_repair(request, pk):
    if not request.user.is_supervisor:
        raise PermissionDenied

    repair = get_object_or_404(RepairRequest, pk=pk)
    try:
        analysis = analyze_repair_request(repair)
    except AIAnalysisError as error:
        messages.error(
            request,
            str(error) if request.LANGUAGE_CODE == 'en'
            else f'วิเคราะห์ด้วย AI ไม่สำเร็จ: {error}',
        )
        return redirect('repair_detail', pk=repair.pk)

    repair.ai_summary_th = analysis['summary_th']
    repair.ai_summary_en = analysis['summary_en']
    repair.ai_suggested_category = analysis['category']
    repair.ai_urgency = analysis['urgency']
    repair.ai_reason_th = analysis['reason_th']
    repair.ai_reason_en = analysis['reason_en']
    repair.ai_summary = analysis['summary_en'] if request.LANGUAGE_CODE == 'en' else analysis['summary_th']
    repair.ai_reason = analysis['reason_en'] if request.LANGUAGE_CODE == 'en' else analysis['reason_th']
    repair.ai_analyzed_at = timezone.now()
    repair.save(update_fields=(
        'ai_summary',
        'ai_summary_th',
        'ai_summary_en',
        'ai_suggested_category',
        'ai_urgency',
        'ai_reason',
        'ai_reason_th',
        'ai_reason_en',
        'ai_analyzed_at',
    ))
    messages.success(
        request,
        'AI suggestions are ready for your review.'
        if request.LANGUAGE_CODE == 'en'
        else 'วิเคราะห์คำร้องแล้ว กรุณาตรวจสอบคำแนะนำจาก AI',
    )
    return redirect('repair_detail', pk=repair.pk)


@login_required
def delete_request(request, pk):
    repair = get_object_or_404(RepairRequest, pk=pk)
    if repair.reported_by != request.user and not request.user.is_supervisor:
        raise PermissionDenied
    if request.method == 'POST':
        repair.delete()
        if request.LANGUAGE_CODE == 'en':
            messages.success(request, 'Repair request deleted.')
        else:
            messages.success(request, 'ลบรายการแจ้งซ่อมเรียบร้อยแล้ว')
    return redirect('dashboard')
