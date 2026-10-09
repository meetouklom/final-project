import logging
from pathlib import Path
from smtplib import SMTPException
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.views.i18n import set_language
from django.views.decorators.http import require_POST
from repairs.models import RepairRequest
from .forms import LocalizedAuthenticationForm, LocalizedSetPasswordForm, RegistrationForm
from .models import AccountAuditLog, User


logger = logging.getLogger(__name__)


def _account_management_redirect(request, account_id=None):
    query = QueryDict(request.POST.get('return_query', ''), mutable=False)
    params = {}
    search = query.get('q', '').strip()[:100]
    role = query.get('role', '')
    status = query.get('status', '')
    page = query.get('page', '')
    if search:
        params['q'] = search
    if role in User.Role.values:
        params['role'] = role
    if status in ('active', 'inactive'):
        params['status'] = status
    if page.isdigit():
        params['page'] = page
    url = reverse('account_management')
    if params:
        url = f'{url}?{urlencode(params)}'
    if account_id:
        url = f'{url}#account-{account_id}'
    return redirect(url)


def _get_member_stats():
    regular_account = Q(is_staff=False, is_superuser=False)
    return User.objects.aggregate(
        total=Count('id'),
        active=Count('id', filter=Q(is_active=True)),
        inactive=Count('id', filter=Q(is_active=False)),
        residents=Count('id', filter=Q(role=User.Role.STUDENT) & regular_account),
        supervisors=Count('id', filter=Q(role=User.Role.SUPERVISOR) & regular_account),
        administrators=Count('id', filter=Q(is_staff=True) | Q(is_superuser=True)),
    )


class LocalizedLoginView(auth_views.LoginView):
    form_class = LocalizedAuthenticationForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['language'] = self.request.LANGUAGE_CODE
        return kwargs


class LocalizedPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    form_class = LocalizedSetPasswordForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['language'] = self.request.LANGUAGE_CODE
        return kwargs


def home(request):
    return render(request, 'home.html')


def features(request):
    return render(request, 'features.html')


def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = RegistrationForm(request.POST or None, language=request.LANGUAGE_CODE)
    if request.method == 'POST' and form.is_valid():
        form.save()
        if request.LANGUAGE_CODE == 'en':
            messages.success(request, 'Registration complete. Please sign in.')
        else:
            messages.success(request, 'สมัครสมาชิกสำเร็จ กรุณาเข้าสู่ระบบ')
        return redirect('login')
    return render(request, 'accounts/register.html', {'form': form})


@login_required
def dashboard(request):
    member_stats = None
    if request.user.is_supervisor:
        requests = RepairRequest.objects.select_related('reported_by').all()
        member_stats = _get_member_stats()
    else:
        requests = RepairRequest.objects.filter(reported_by=request.user)
    status_totals = {
        row['status']: row['count']
        for row in requests.values('status').annotate(count=Count('id'))
    }
    total = sum(status_totals.values())
    status_breakdown = [
        {
            'key': status,
            'count': status_totals.get(status, 0),
            'percent': round(status_totals.get(status, 0) * 100 / total) if total else 0,
        }
        for status, _ in RepairRequest.Status.choices
    ]
    stats = {
        'total': total,
        'open': sum(status_totals.get(status, 0) for status in (
            RepairRequest.Status.RECEIVED,
            RepairRequest.Status.IN_PROGRESS,
            RepairRequest.Status.WAITING,
        )),
        'completed': status_totals.get(RepairRequest.Status.COMPLETED, 0),
        'waiting': status_totals.get(RepairRequest.Status.WAITING, 0),
        'completion_percent': round(status_totals.get(RepairRequest.Status.COMPLETED, 0) * 100 / total) if total else 0,
    }
    return render(request, 'dashboard.html', {
        'repair_requests': requests[:20],
        'stats': stats,
        'status_breakdown': status_breakdown,
        'member_stats': member_stats,
    })


@login_required
def admin_er_diagram(request):
    if not request.user.is_superuser:
        raise PermissionDenied
    return render(request, 'admin/er_diagram.html')


@login_required
def admin_er_diagram_image(request):
    if not request.user.is_superuser:
        raise PermissionDenied
    diagram_path = Path(__file__).resolve().parent.parent / 'docs' / 'DORMFIX_ER_DIAGRAM.svg'
    return FileResponse(diagram_path.open('rb'), content_type='image/svg+xml')


@login_required
def account_management(request):
    if not request.user.is_supervisor:
        raise PermissionDenied

    accounts = User.objects.order_by('username', 'pk')
    search = request.GET.get('q', '').strip()[:100]
    role = request.GET.get('role', '')
    status = request.GET.get('status', '')
    if search:
        accounts = accounts.filter(
            Q(username__icontains=search)
            | Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(email__icontains=search)
        )
    if role in User.Role.values:
        accounts = accounts.filter(role=role)
    else:
        role = ''
    if status == 'active':
        accounts = accounts.filter(is_active=True)
    elif status == 'inactive':
        accounts = accounts.filter(is_active=False)
    else:
        status = ''

    page_obj = Paginator(accounts, 25).get_page(request.GET.get('page'))
    filter_params = {
        key: value
        for key, value in (
            ('q', search),
            ('role', role),
            ('status', status),
        )
        if value
    }
    member_stats = _get_member_stats()
    return render(request, 'accounts/management.html', {
        'page_obj': page_obj,
        'accounts': page_obj.object_list,
        'search': search,
        'role_filter': role,
        'status_filter': status,
        'filter_query': urlencode(filter_params),
        'member_stats': member_stats,
    })


@login_required
def account_activity(request):
    if not request.user.is_supervisor:
        raise PermissionDenied

    entries = AccountAuditLog.objects.select_related('actor', 'target')
    search = request.GET.get('q', '').strip()[:100]
    action = request.GET.get('action', '')
    if search:
        entries = entries.filter(
            Q(actor_username__icontains=search)
            | Q(target_username__icontains=search)
            | Q(old_value__icontains=search)
            | Q(new_value__icontains=search)
        )
    if action in AccountAuditLog.Action.values:
        entries = entries.filter(action=action)
    else:
        action = ''
    page_obj = Paginator(entries, 30).get_page(request.GET.get('page'))
    filter_params = {
        key: value
        for key, value in (('q', search), ('action', action))
        if value
    }
    return render(request, 'accounts/activity.html', {
        'page_obj': page_obj,
        'entries': page_obj.object_list,
        'search': search,
        'action_filter': action,
        'action_choices': AccountAuditLog.Action.choices,
        'filter_query': urlencode(filter_params),
    })


@login_required
@require_POST
def update_account_role(request, user_id):
    if not request.user.is_supervisor:
        raise PermissionDenied

    role = request.POST.get('role')
    if role not in User.Role.values:
        messages.error(
            request,
            'Choose a valid account role.'
            if request.LANGUAGE_CODE == 'en'
            else 'กรุณาเลือกประเภทบัญชีที่ถูกต้อง',
        )
        return _account_management_redirect(request, user_id)

    with transaction.atomic():
        active_supervisor_ids = list(
            User.objects.select_for_update().filter(
                role=User.Role.SUPERVISOR,
                is_active=True,
                is_staff=False,
                is_superuser=False,
            ).values_list('pk', flat=True)
        )
        account = get_object_or_404(
            User.objects.select_for_update(),
            pk=user_id,
            is_staff=False,
            is_superuser=False,
        )
        if account.pk == request.user.pk:
            messages.error(
                request,
                'You cannot change your own account role.'
                if request.LANGUAGE_CODE == 'en'
                else 'ไม่สามารถเปลี่ยนบทบาทบัญชีของตนเองได้',
            )
            return _account_management_redirect(request, user_id)

        if account.role == role:
            messages.info(
                request,
                'The account already has that role.'
                if request.LANGUAGE_CODE == 'en'
                else 'บัญชีนี้มีบทบาทดังกล่าวอยู่แล้ว',
            )
            return _account_management_redirect(request, user_id)

        if (
            account.is_active
            and account.is_supervisor
            and role == User.Role.STUDENT
            and len(active_supervisor_ids) <= 1
        ):
            messages.error(
                request,
                'The last active supervisor cannot be changed to a resident.'
                if request.LANGUAGE_CODE == 'en'
                else 'ไม่สามารถเปลี่ยนผู้ดูแลคนสุดท้ายให้เป็นผู้พักอาศัยได้',
            )
            return _account_management_redirect(request, user_id)

        old_role = account.role
        account.role = role
        account.save(update_fields=('role',))
        AccountAuditLog.objects.create(
            actor=request.user,
            actor_username=request.user.username,
            target=account,
            target_username=account.username,
            action=AccountAuditLog.Action.ROLE_CHANGED,
            old_value=old_role,
            new_value=role,
        )

    role_labels = {
        User.Role.SUPERVISOR: {
            'en': 'Dormitory supervisor',
            'th': 'ผู้ดูแลหอพัก',
        },
        User.Role.STUDENT: {
            'en': 'Resident',
            'th': 'ผู้พักอาศัย',
        },
    }
    role_label = role_labels[role][request.LANGUAGE_CODE if request.LANGUAGE_CODE == 'en' else 'th']
    messages.success(
        request,
        f'{account.username} is now a {role_label}.'
        if request.LANGUAGE_CODE == 'en'
        else f'เปลี่ยนบทบาทของ {account.username} เป็น{role_label}แล้ว',
    )
    return _account_management_redirect(request, user_id)


@login_required
@require_POST
def update_account_status(request, user_id):
    if not request.user.is_supervisor:
        raise PermissionDenied

    requested_status = request.POST.get('is_active')
    if requested_status not in ('true', 'false'):
        messages.error(
            request,
            'Choose a valid account status.'
            if request.LANGUAGE_CODE == 'en'
            else 'กรุณาเลือกสถานะบัญชีที่ถูกต้อง',
        )
        return _account_management_redirect(request, user_id)

    is_active = requested_status == 'true'
    with transaction.atomic():
        active_supervisor_ids = list(
            User.objects.select_for_update().filter(
                role=User.Role.SUPERVISOR,
                is_active=True,
                is_staff=False,
                is_superuser=False,
            ).values_list('pk', flat=True)
        )
        account = get_object_or_404(
            User.objects.select_for_update(),
            pk=user_id,
            is_staff=False,
            is_superuser=False,
        )
        if account.pk == request.user.pk and not is_active:
            messages.error(
                request,
                'You cannot deactivate your own account.'
                if request.LANGUAGE_CODE == 'en'
                else 'ไม่สามารถปิดใช้งานบัญชีของตนเองได้',
            )
            return _account_management_redirect(request, user_id)

        if account.is_active == is_active:
            messages.info(
                request,
                'The account already has that status.'
                if request.LANGUAGE_CODE == 'en'
                else 'บัญชีนี้มีสถานะดังกล่าวอยู่แล้ว',
            )
            return _account_management_redirect(request, user_id)

        if (
            account.is_active
            and not is_active
            and account.is_supervisor
            and len(active_supervisor_ids) <= 1
        ):
            messages.error(
                request,
                'The last active supervisor cannot be deactivated.'
                if request.LANGUAGE_CODE == 'en'
                else 'ไม่สามารถปิดใช้งานผู้ดูแลคนสุดท้ายได้',
            )
            return _account_management_redirect(request, user_id)

        account.is_active = is_active
        account.save(update_fields=('is_active',))
        AccountAuditLog.objects.create(
            actor=request.user,
            actor_username=request.user.username,
            target=account,
            target_username=account.username,
            action=(
                AccountAuditLog.Action.ACCOUNT_ACTIVATED
                if is_active
                else AccountAuditLog.Action.ACCOUNT_DEACTIVATED
            ),
            old_value='inactive' if is_active else 'active',
            new_value='active' if is_active else 'inactive',
        )

    messages.success(
        request,
        f'{account.username} is now {"active" if is_active else "inactive"}.'
        if request.LANGUAGE_CODE == 'en'
        else f'เปลี่ยนสถานะบัญชี {account.username} เป็น{"ใช้งาน" if is_active else "ปิดใช้งาน"}แล้ว',
    )
    return _account_management_redirect(request, user_id)


@login_required
@require_POST
def send_account_password_reset(request, user_id):
    if not request.user.is_supervisor:
        raise PermissionDenied

    resident = get_object_or_404(
        User,
        pk=user_id,
        role=User.Role.STUDENT,
        is_active=True,
        is_staff=False,
        is_superuser=False,
    )
    if not resident.email:
        messages.error(
            request,
            'This account has no email address.'
            if request.LANGUAGE_CODE == 'en'
            else 'บัญชีนี้ยังไม่มีอีเมล',
        )
        return _account_management_redirect(request, user_id)

    uid = urlsafe_base64_encode(force_bytes(resident.pk))
    token = default_token_generator.make_token(resident)
    reset_url = request.build_absolute_uri(reverse(
        'password_reset_confirm',
        kwargs={'uidb64': uid, 'token': token},
    ))
    is_english = request.LANGUAGE_CODE == 'en'
    subject = (
        'Reset your DormFix password'
        if is_english
        else 'ตั้งรหัสผ่าน DormFix ใหม่'
    )
    greeting = resident.get_full_name() or resident.username
    if is_english:
        message = (
            f'Hello {greeting},\n\n'
            'A dormitory supervisor requested a password reset for your DormFix account. '
            'Use this secure link to choose a new password:\n'
            f'{reset_url}\n\n'
            'If you did not expect this email, you can ignore it. Your current password '
            'will remain unchanged until a new one is set.'
        )
    else:
        message = (
            f'สวัสดี {greeting}\n\n'
            'ผู้ดูแลหอพักส่งคำขอให้ตั้งรหัสผ่าน DormFix ใหม่ '
            'กรุณาเปิดลิงก์ที่ปลอดภัยนี้เพื่อตั้งรหัสผ่านใหม่:\n'
            f'{reset_url}\n\n'
            'หากคุณไม่ได้คาดว่าจะได้รับอีเมลนี้ สามารถละเว้นได้ '
            'รหัสผ่านปัจจุบันจะยังใช้ได้จนกว่าจะตั้งรหัสผ่านใหม่'
        )

    try:
        sent_count = send_mail(subject, message, None, [resident.email], fail_silently=False)
    except (OSError, SMTPException):
        logger.exception('Failed to send password reset email for user id %s', resident.pk)
        sent_count = 0

    if sent_count:
        messages.success(
            request,
            f'Password reset link sent to {resident.email}.'
            if is_english
            else f'ส่งลิงก์ตั้งรหัสผ่านใหม่ไปที่ {resident.email} แล้ว',
        )
    else:
        messages.error(
            request,
            'Could not send the email. Check the email server settings and try again.'
            if is_english
            else 'ส่งอีเมลไม่สำเร็จ กรุณาตรวจสอบการตั้งค่าอีเมลแล้วลองอีกครั้ง',
        )
    return _account_management_redirect(request, user_id)


@login_required
def account_settings(request):
    return render(request, 'accounts/settings.html')


@login_required
def delete_account(request):
    error = None
    if request.method == 'POST':
        password = request.POST.get('password', '')
        if request.user.check_password(password):
            username = request.user.username
            request.user.delete()
            logout(request)
            messages.success(
                request,
                'Account deleted successfully.'
                if request.LANGUAGE_CODE == 'en'
                else 'ลบบัญชีเรียบร้อยแล้ว',
            )
            return redirect('login')
        error = (
            'Password is incorrect. Please try again.'
            if request.LANGUAGE_CODE == 'en'
            else 'รหัสผ่านไม่ถูกต้อง กรุณาลองอีกครั้ง'
        )
    return render(request, 'accounts/delete_account.html', {'error': error})


def language_switch(request):
    return set_language(request)
