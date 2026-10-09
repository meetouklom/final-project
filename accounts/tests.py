import re

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from repairs.models import RepairRequest
from .models import AccountAuditLog, User


class HomePageTests(TestCase):
    def test_home_page_is_public_and_brand_links_back_to_it(self):
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/"')
        self.assertContains(response, 'จัดการง่ายขึ้น')
        self.assertEqual(response.content.count(b'class="home-primary"'), 1)
        self.assertNotContains(response, 'home-benefits')
        self.assertContains(response, 'class="home-secondary"')
        self.assertContains(response, 'class="header-sign-in"')
        self.assertNotContains(response, 'Already have an account?')
        self.assertContains(response, 'ดูสถานะล่าสุดของทุกคำขอได้ง่าย ๆ')

    def test_home_page_keeps_one_primary_action_for_signed_in_users(self):
        user = User.objects.create_user(username='student', password='pass-1234')
        self.client.force_login(user)

        response = self.client.get(reverse('home'))

        self.assertEqual(response.content.count(b'class="home-primary"'), 1)
        self.assertContains(response, 'ไปที่แดชบอร์ด')
        self.assertContains(response, 'ต้องการแจ้งซ่อม?')

    def test_home_page_localizes_primary_action_and_feature_cards(self):
        response = self.client.get(reverse('home'), HTTP_ACCEPT_LANGUAGE='en')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Get started')
        self.assertContains(response, 'class="home-secondary"')
        self.assertContains(response, 'class="header-sign-in"')
        self.assertEqual(response.content.count(b'Sign in'), 2)
        self.assertContains(response, 'Tell your dorm team what needs fixing.')
        self.assertContains(response, 'See the latest status of every request.')

    def test_dashboard_is_available_at_its_own_url_after_sign_in(self):
        user = User.objects.create_user(username='student', password='pass-1234')
        self.client.force_login(user)

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/dashboard/"')
        self.assertContains(response, '<strong>student</strong>')
        self.assertContains(response, 'class="user-avatar" aria-hidden="true">S</span>')
        self.assertNotContains(response, '{{ request.user.get_full_name')
        navigation = response.content.split(b'<nav class="sidebar-nav"', 1)[1].split(b'</nav>', 1)[0]
        self.assertLess(navigation.index(b'href="/dashboard/"'), navigation.index(b'href="/repairs/new/"'))
        self.assertNotIn(b'>Home<', navigation)
        self.assertNotIn(b'>Features<', navigation)

    def test_public_navigation_shows_home_and_features_without_app_links(self):
        response = self.client.get(reverse('home'))
        navigation = response.content.split(b'<nav class="sidebar-nav"', 1)[1].split(b'</nav>', 1)[0]

        self.assertIn(b'href="/"', navigation)
        self.assertIn(b'href="/features/"', navigation)
        self.assertNotIn(b'href="/dashboard/"', navigation)
        self.assertNotIn(b'href="/repairs/new/"', navigation)

    def test_dashboard_requires_sign_in(self):
        response = self.client.get(reverse('dashboard'))

        self.assertRedirects(response, f"{reverse('login')}?next={reverse('dashboard')}")

    def test_account_settings_requires_sign_in(self):
        response = self.client.get(reverse('account_settings'))

        self.assertRedirects(response, f"{reverse('login')}?next={reverse('account_settings')}")

    def test_account_settings_contains_account_deletion_and_dropdown_stays_safe(self):
        user = User.objects.create_user(username='student', password='pass-1234', email='student@example.com')
        self.client.force_login(user)

        response = self.client.get(reverse('account_settings'))

        self.assertContains(response, 'student@example.com')
        self.assertContains(response, reverse('delete_account'))
        self.assertContains(response, reverse('account_settings'))
        self.assertNotContains(response, 'profile-delete-account')
        self.assertContains(response, 'ออกจากระบบ')

    def test_supervisor_dashboard_shows_member_counts_and_management_link_without_passwords(self):
        supervisor = User.objects.create_user(
            username='supervisor',
            password='pass-1234',
            role=User.Role.SUPERVISOR,
        )
        resident = User.objects.create_user(
            username='resident',
            password='Resident-Secret-123!',
            email='resident@example.com',
            role=User.Role.STUDENT,
        )
        other_supervisor = User.objects.create_user(
            username='other-supervisor',
            password='pass-1234',
            role=User.Role.SUPERVISOR,
        )
        User.objects.create_superuser(
            username='root',
            password='pass-1234',
            email='root@example.com',
        )
        self.client.force_login(supervisor)

        response = self.client.get(reverse('dashboard'))

        self.assertContains(response, reverse('account_management'))
        self.assertContains(response, 'ภาพรวมบัญชีผู้ใช้')
        self.assertEqual(response.context['member_stats']['total'], 4)
        self.assertEqual(response.context['member_stats']['active'], 4)
        self.assertEqual(response.context['member_stats']['residents'], 1)
        self.assertEqual(response.context['member_stats']['supervisors'], 2)
        self.assertEqual(response.context['member_stats']['administrators'], 1)
        self.assertNotContains(response, 'resident@example.com')
        self.assertNotContains(response, 'other-supervisor')
        self.assertNotContains(response, 'Resident-Secret-123!')
        self.assertNotContains(response, other_supervisor.password)

    def test_account_management_lists_accounts_in_pages_of_twenty_five(self):
        supervisor = User.objects.create_user(
            username='supervisor',
            password='pass-1234',
            role=User.Role.SUPERVISOR,
        )
        residents = [
            User.objects.create_user(
                username=f'resident-{number:02d}',
                password='pass-1234',
                role=User.Role.STUDENT,
            )
            for number in range(11)
        ]
        self.client.force_login(supervisor)

        response = self.client.get(reverse('account_management'))

        self.assertEqual(len(response.context['accounts']), 12)
        self.assertEqual(response.context['page_obj'].paginator.per_page, 25)
        self.assertContains(response, residents[10].username)
        self.assertContains(response, reverse('update_account_role', args=[residents[10].pk]))

    def test_account_management_paginates_search_and_status_filters(self):
        supervisor = User.objects.create_user(
            username='supervisor',
            password='pass-1234',
            role=User.Role.SUPERVISOR,
        )
        residents = [
            User.objects.create_user(
                username=f'resident-{number:02d}',
                password='pass-1234',
                role=User.Role.STUDENT,
            )
            for number in range(11)
        ]
        residents[-1].is_active = False
        residents[-1].save(update_fields=('is_active',))
        self.client.force_login(supervisor)

        filtered = self.client.get(reverse('account_management'), {
            'q': 'resident-10',
            'status': 'inactive',
        })
        self.assertEqual(filtered.status_code, 200)
        self.assertEqual(list(filtered.context['accounts']), [residents[-1]])
        self.assertContains(filtered, 'resident-10')

        for number in range(25):
            User.objects.create_user(
                username=f'page-resident-{number:02d}',
                password='pass-1234',
                role=User.Role.STUDENT,
            )
        paginated = self.client.get(reverse('account_management'), {'page': '2'})
        self.assertEqual(paginated.context['page_obj'].number, 2)
        self.assertTrue(paginated.context['page_obj'].has_previous())

    def test_account_management_requires_supervisor(self):
        resident = User.objects.create_user(username='resident', password='pass-1234')
        self.client.force_login(resident)

        response = self.client.get(reverse('account_management'))

        self.assertEqual(response.status_code, 403)

    def test_account_management_protects_django_admin_accounts(self):
        supervisor = User.objects.create_user(
            username='supervisor',
            password='pass-1234',
            role=User.Role.SUPERVISOR,
        )
        administrator = User.objects.create_superuser(
            username='root',
            password='pass-1234',
            email='root@example.com',
        )
        self.client.force_login(supervisor)

        response = self.client.get(reverse('account_management'))

        self.assertContains(response, 'Django Admin')
        self.assertContains(response, reverse('admin:accounts_user_change', args=[administrator.pk]))
        self.assertNotContains(response, reverse('update_account_status', args=[administrator.pk]))

    def test_supervisor_can_deactivate_and_reactivate_accounts_without_deleting_them(self):
        supervisor = User.objects.create_user(
            username='supervisor',
            password='pass-1234',
            role=User.Role.SUPERVISOR,
        )
        resident = User.objects.create_user(
            username='resident',
            password='pass-1234',
            role=User.Role.STUDENT,
        )
        self.client.force_login(supervisor)
        url = reverse('update_account_status', args=[resident.pk])

        deactivated = self.client.post(url, {'is_active': 'false'})
        self.assertRedirects(deactivated, reverse('account_management') + f'#account-{resident.pk}')
        resident.refresh_from_db()
        self.assertFalse(resident.is_active)
        self.assertTrue(User.objects.filter(pk=resident.pk).exists())

        reactivated = self.client.post(url, {'is_active': 'true'})
        self.assertRedirects(reactivated, reverse('account_management') + f'#account-{resident.pk}')
        resident.refresh_from_db()
        self.assertTrue(resident.is_active)
        entries = list(AccountAuditLog.objects.order_by('created_at', 'pk'))
        self.assertEqual(
            [entry.action for entry in entries],
            [
                AccountAuditLog.Action.ACCOUNT_DEACTIVATED,
                AccountAuditLog.Action.ACCOUNT_ACTIVATED,
            ],
        )
        self.assertTrue(all(entry.actor == supervisor for entry in entries))
        self.assertTrue(all(entry.target == resident for entry in entries))
        self.assertEqual(entries[0].actor_username, supervisor.username)
        self.assertEqual(entries[0].target_username, resident.username)
        self.assertEqual((entries[0].old_value, entries[0].new_value), ('active', 'inactive'))
        self.assertEqual((entries[1].old_value, entries[1].new_value), ('inactive', 'active'))

    def test_account_management_confirms_deactivation_and_explains_history_is_kept(self):
        supervisor = User.objects.create_user(
            username='supervisor',
            password='pass-1234',
            role=User.Role.SUPERVISOR,
        )
        resident = User.objects.create_user(username='resident', password='pass-1234')
        self.client.force_login(supervisor)

        response = self.client.get(reverse('account_management'))

        self.assertContains(response, 'data-confirm-deactivation-form')
        self.assertContains(response, 'data-account-confirm-dialog')
        self.assertContains(response, 'ประวัติการแจ้งซ่อมจะยังคงอยู่')
        self.assertContains(response, 'ไม่ถูกลบ')
        self.assertContains(response, f'id="account-{resident.pk}"')

    def test_role_changes_are_recorded_with_actor_and_before_after_values(self):
        supervisor = User.objects.create_user(
            username='supervisor',
            password='pass-1234',
            role=User.Role.SUPERVISOR,
        )
        resident = User.objects.create_user(username='resident', password='pass-1234')
        self.client.force_login(supervisor)

        response = self.client.post(
            reverse('update_account_role', args=[resident.pk]),
            {'role': User.Role.SUPERVISOR},
        )

        self.assertEqual(response.status_code, 302)
        entry = AccountAuditLog.objects.get()
        self.assertEqual(entry.action, AccountAuditLog.Action.ROLE_CHANGED)
        self.assertEqual(entry.actor, supervisor)
        self.assertEqual(entry.actor_username, supervisor.username)
        self.assertEqual(entry.target, resident)
        self.assertEqual(entry.target_username, resident.username)
        self.assertEqual(entry.old_value, User.Role.STUDENT)
        self.assertEqual(entry.new_value, User.Role.SUPERVISOR)

    def test_supervisor_can_search_and_filter_account_activity(self):
        supervisor = User.objects.create_user(
            username='supervisor',
            password='pass-1234',
            role=User.Role.SUPERVISOR,
        )
        resident = User.objects.create_user(username='resident', password='pass-1234')
        other = User.objects.create_user(username='other', password='pass-1234')
        AccountAuditLog.objects.create(
            actor=supervisor,
            actor_username=supervisor.username,
            target=resident,
            target_username=resident.username,
            action=AccountAuditLog.Action.ROLE_CHANGED,
            old_value=User.Role.STUDENT,
            new_value=User.Role.SUPERVISOR,
        )
        AccountAuditLog.objects.create(
            actor=supervisor,
            actor_username=supervisor.username,
            target=other,
            target_username=other.username,
            action=AccountAuditLog.Action.ACCOUNT_DEACTIVATED,
            old_value='active',
            new_value='inactive',
        )
        self.client.force_login(supervisor)

        response = self.client.get(reverse('account_activity'), {
            'q': 'resident',
            'action': AccountAuditLog.Action.ROLE_CHANGED,
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['entries']), 1)
        self.assertContains(response, 'resident')
        self.assertNotContains(response, 'other')
        self.assertContains(response, 'ผู้ดูแลหอพัก')

    def test_resident_cannot_view_account_activity_and_deleted_accounts_keep_audit_snapshots(self):
        supervisor = User.objects.create_user(
            username='supervisor',
            password='pass-1234',
            role=User.Role.SUPERVISOR,
        )
        resident = User.objects.create_user(username='resident', password='pass-1234')
        entry = AccountAuditLog.objects.create(
            actor=supervisor,
            actor_username=supervisor.username,
            target=resident,
            target_username=resident.username,
            action=AccountAuditLog.Action.ACCOUNT_DEACTIVATED,
            old_value='active',
            new_value='inactive',
        )
        resident.delete()
        self.client.force_login(supervisor)

        response = self.client.get(reverse('account_activity'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'resident')
        entry.refresh_from_db()
        self.assertIsNone(entry.target)
        self.assertEqual(entry.target_username, 'resident')

        self.client.force_login(User.objects.create_user(username='reader', password='pass-1234'))
        forbidden_response = self.client.get(reverse('account_activity'))
        self.assertEqual(forbidden_response.status_code, 403)

    def test_supervisor_cannot_deactivate_themselves_or_last_supervisor(self):
        supervisor = User.objects.create_user(
            username='supervisor',
            password='pass-1234',
            role=User.Role.SUPERVISOR,
        )
        self.client.force_login(supervisor)
        self_deactivation = self.client.post(
            reverse('update_account_status', args=[supervisor.pk]),
            {'is_active': 'false'},
        )
        self.assertRedirects(
            self_deactivation,
            reverse('account_management') + f'#account-{supervisor.pk}',
        )
        supervisor.refresh_from_db()
        self.assertTrue(supervisor.is_active)

        manager = User.objects.create_user(
            username='staff-supervisor',
            password='pass-1234',
            role=User.Role.SUPERVISOR,
            is_staff=True,
        )
        self.client.force_login(manager)
        last_supervisor = self.client.post(
            reverse('update_account_status', args=[supervisor.pk]),
            {'is_active': 'false'},
        )
        self.assertRedirects(
            last_supervisor,
            reverse('account_management') + f'#account-{supervisor.pk}',
        )
        supervisor.refresh_from_db()
        self.assertTrue(supervisor.is_active)

    def test_supervisor_can_change_an_account_role(self):
        supervisor = User.objects.create_user(
            username='supervisor',
            password='pass-1234',
            role=User.Role.SUPERVISOR,
        )
        resident = User.objects.create_user(
            username='resident',
            password='pass-1234',
            role=User.Role.STUDENT,
        )
        self.client.force_login(supervisor)

        response = self.client.post(
            reverse('update_account_role', args=[resident.pk]),
            {'role': User.Role.SUPERVISOR},
        )

        self.assertRedirects(response, reverse('account_management') + f'#account-{resident.pk}')
        resident.refresh_from_db()
        self.assertEqual(resident.role, User.Role.SUPERVISOR)

    def test_resident_cannot_change_account_roles(self):
        resident = User.objects.create_user(
            username='resident',
            password='pass-1234',
            role=User.Role.STUDENT,
        )
        target = User.objects.create_user(
            username='target',
            password='pass-1234',
            role=User.Role.STUDENT,
        )
        self.client.force_login(resident)

        response = self.client.post(
            reverse('update_account_role', args=[target.pk]),
            {'role': User.Role.SUPERVISOR},
        )

        self.assertEqual(response.status_code, 403)
        target.refresh_from_db()
        self.assertEqual(target.role, User.Role.STUDENT)

    def test_supervisor_cannot_change_their_own_role(self):
        supervisor = User.objects.create_user(
            username='supervisor',
            password='pass-1234',
            role=User.Role.SUPERVISOR,
        )
        self.client.force_login(supervisor)

        response = self.client.post(
            reverse('update_account_role', args=[supervisor.pk]),
            {'role': User.Role.STUDENT},
        )

        self.assertRedirects(response, reverse('account_management') + f'#account-{supervisor.pk}')
        supervisor.refresh_from_db()
        self.assertEqual(supervisor.role, User.Role.SUPERVISOR)

    def test_role_change_rejects_invalid_roles_and_protected_accounts(self):
        supervisor = User.objects.create_user(
            username='supervisor',
            password='pass-1234',
            role=User.Role.SUPERVISOR,
        )
        resident = User.objects.create_user(
            username='resident',
            password='pass-1234',
            role=User.Role.STUDENT,
        )
        self.client.force_login(supervisor)

        invalid_role_response = self.client.post(
            reverse('update_account_role', args=[resident.pk]),
            {'role': 'administrator'},
        )
        self.assertRedirects(invalid_role_response, reverse('account_management') + f'#account-{resident.pk}')
        resident.refresh_from_db()
        self.assertEqual(resident.role, User.Role.STUDENT)

        protected_account = User.objects.create_superuser(
            username='root',
            password='pass-1234',
            email='root@example.com',
        )
        protected_response = self.client.post(
            reverse('update_account_role', args=[protected_account.pk]),
            {'role': User.Role.STUDENT},
        )
        self.assertEqual(protected_response.status_code, 404)

    def test_supervisor_can_send_a_single_use_password_reset_link(self):
        supervisor = User.objects.create_user(
            username='supervisor',
            password='pass-1234',
            role=User.Role.SUPERVISOR,
        )
        resident = User.objects.create_user(
            username='resident',
            password='old-password-123',
            email='resident@example.com',
            role=User.Role.STUDENT,
        )
        self.client.force_login(supervisor)

        response = self.client.post(reverse('send_account_password_reset', args=[resident.pk]))

        self.assertRedirects(response, reverse('account_management') + f'#account-{resident.pk}')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['resident@example.com'])
        self.assertIn('password-reset', mail.outbox[0].body)
        self.assertTrue(resident.check_password('old-password-123'))

        reset_path = re.search(r'http://testserver(/\S+)', mail.outbox[0].body).group(1)
        reset_page = self.client.get(reset_path, follow=True)
        self.assertContains(reset_page, 'ตั้งรหัสผ่านใหม่')
        response = self.client.post(reset_page.wsgi_request.path, {
            'new_password1': 'New-Resident-Password-567!',
            'new_password2': 'New-Resident-Password-567!',
        })

        self.assertRedirects(response, reverse('password_reset_complete'))
        resident.refresh_from_db()
        self.assertTrue(resident.check_password('New-Resident-Password-567!'))
        self.assertFalse(resident.check_password('old-password-123'))
        reset_again = self.client.get(reset_path, follow=True)
        self.assertContains(reset_again, 'ลิงก์นี้หมดอายุแล้ว')

    def test_residents_cannot_send_password_reset_links_for_other_accounts(self):
        resident = User.objects.create_user(
            username='resident',
            password='pass-1234',
            role=User.Role.STUDENT,
        )
        target = User.objects.create_user(
            username='target',
            password='pass-1234',
            email='target@example.com',
            role=User.Role.STUDENT,
        )
        self.client.force_login(resident)

        response = self.client.post(reverse('send_account_password_reset', args=[target.pk]))

        self.assertEqual(response.status_code, 403)
        self.assertEqual(len(mail.outbox), 0)

    def test_supervisor_cannot_send_reset_link_for_account_without_email(self):
        supervisor = User.objects.create_user(
            username='supervisor',
            password='pass-1234',
            role=User.Role.SUPERVISOR,
        )
        resident = User.objects.create_user(
            username='resident',
            password='pass-1234',
            role=User.Role.STUDENT,
        )
        self.client.force_login(supervisor)

        response = self.client.post(reverse('send_account_password_reset', args=[resident.pk]))

        self.assertRedirects(
            response,
            reverse('account_management') + f'#account-{resident.pk}',
            fetch_redirect_response=False,
        )
        self.assertEqual(len(mail.outbox), 0)
        self.assertContains(self.client.get(reverse('account_management')), 'บัญชีนี้ยังไม่มีอีเมล')

    def test_dashboard_summarizes_only_the_signed_in_students_requests(self):
        user = User.objects.create_user(username='student', password='pass-1234')
        another_student = User.objects.create_user(username='another', password='pass-1234')
        RepairRequest.objects.create(
            reported_by=user, title='Broken light', category='electricity',
            location='A-101', description='Light is out.',
        )
        RepairRequest.objects.create(
            reported_by=user, title='Leaking tap', category='plumbing',
            location='A-101', description='Tap is leaking.',
            status=RepairRequest.Status.COMPLETED,
        )
        RepairRequest.objects.create(
            reported_by=another_student, title='Private issue', category='other',
            location='B-202', description='Private.',
        )
        self.client.force_login(user)

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.context['stats']['total'], 2)
        self.assertEqual(response.context['stats']['open'], 1)
        self.assertEqual(response.context['stats']['completed'], 1)
        self.assertEqual(response.context['stats']['completion_percent'], 50)
        self.assertEqual(response.context['status_breakdown'][0]['count'], 1)
        self.assertNotContains(response, 'Private issue')

    def test_features_page_is_public_and_available_from_navigation(self):
        response = self.client.get(reverse('features'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ฟีเจอร์')
        self.assertContains(response, 'href="/features/"')
        self.assertContains(response, 'แนบรูปประกอบ')

    def test_features_page_has_english_content_after_language_switch(self):
        self.client.post(reverse('set_language'), {'language': 'en', 'next': '/features/'})

        response = self.client.get(reverse('features'))

        self.assertContains(response, 'Everything you need to manage dorm repairs.')
        self.assertContains(response, 'Attach a photo')


class AdminERDiagramTests(TestCase):
    def test_only_superusers_can_view_the_er_diagram_and_its_image(self):
        admin_user = User.objects.create_superuser(
            username='root',
            password='pass-1234',
        )
        self.client.force_login(admin_user)

        page = self.client.get(reverse('admin_er_diagram'))
        image = self.client.get(reverse('admin_er_diagram_image'))

        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'แผนภาพ ER ของ DormFix')
        self.assertContains(page, reverse('admin_er_diagram_image'))
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image['Content-Type'], 'image/svg+xml')
        self.assertIn(b'DormFix entity relationship diagram', b''.join(image.streaming_content))

    def test_residents_and_staff_without_superuser_access_are_forbidden(self):
        users = (
            User.objects.create_user(username='resident', password='pass-1234'),
            User.objects.create_user(
                username='staff',
                password='pass-1234',
                is_staff=True,
            ),
        )
        for user in users:
            with self.subTest(username=user.username):
                self.client.force_login(user)
                self.assertEqual(self.client.get(reverse('admin_er_diagram')).status_code, 403)
                self.assertEqual(self.client.get(reverse('admin_er_diagram_image')).status_code, 403)

    def test_er_diagram_navigation_is_shown_only_to_superusers(self):
        admin_user = User.objects.create_superuser(username='root', password='pass-1234')
        self.client.force_login(admin_user)
        admin_dashboard = self.client.get(reverse('dashboard'))
        self.assertContains(admin_dashboard, reverse('admin_er_diagram'))

        resident = User.objects.create_user(username='resident', password='pass-1234')
        self.client.force_login(resident)
        resident_dashboard = self.client.get(reverse('dashboard'))
        self.assertNotContains(resident_dashboard, reverse('admin_er_diagram'))


class AuthenticationPageTests(TestCase):
    def test_registration_page_only_offers_the_resident_role(self):
        response = self.client.get(reverse('register'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'register-grid')
        self.assertContains(response, 'role-options')
        self.assertContains(response, 'ประเภทผู้ใช้งาน')
        self.assertContains(response, 'นักศึกษา')
        self.assertNotContains(response, 'ผู้ดูแลหอพัก')
        self.assertContains(response, 'ชื่อ')
        self.assertContains(response, 'นามสกุล')

    def test_registration_page_localizes_labels_in_english(self):
        response = self.client.get(reverse('register'), HTTP_ACCEPT_LANGUAGE='en')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'First name')
        self.assertContains(response, 'Last name')
        self.assertContains(response, 'Student')
        self.assertNotContains(response, 'Dormitory Supervisor')
        self.assertContains(response, 'I live in the dorm')

    def test_public_registration_cannot_assign_supervisor_role(self):
        response = self.client.post(reverse('register'), {
            'first_name': 'New',
            'last_name': 'Resident',
            'username': 'new-resident',
            'email': 'resident@example.com',
            'role': User.Role.SUPERVISOR,
            'room_number': 'A-101',
            'password1': 'Safe-Password-567!',
            'password2': 'Safe-Password-567!',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='new-resident').exists())
        self.assertTrue(response.context['form'].errors.get('role'))

    def test_login_page_localizes_field_labels_and_error_copy(self):
        response = self.client.get(reverse('login'), HTTP_ACCEPT_LANGUAGE='en')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Username')
        self.assertContains(response, 'Password')
        self.assertContains(response, 'Welcome back')
        self.assertContains(response, 'data-auth-form')
        self.assertContains(response, 'data-loading-label="Signing in..."')
        self.assertContains(response, 'data-page-progress')
        self.assertContains(response, 'data-auth-portal')
        self.assertContains(response, 'data-authenticating="Authenticating securely..."')
        self.assertContains(response, 'data-signin-success="Signed in successfully"')
        self.assertContains(response, 'auth-submit-spinner')

    def test_auth_loading_labels_are_localized_on_both_pages(self):
        login_response = self.client.get(reverse('login'))
        register_response = self.client.get(reverse('register'))

        self.assertContains(login_response, 'data-loading-label="กำลังเข้าสู่ระบบ..."')
        self.assertContains(register_response, 'data-loading-label="กำลังสร้างบัญชี..."')
        self.assertContains(login_response, 'data-preparing="กำลังเตรียมแดชบอร์ดของคุณ..."')
        self.assertContains(register_response, 'class="portal-skeleton"')

        english_login = self.client.get(reverse('login'), HTTP_ACCEPT_LANGUAGE='en')
        english_register = self.client.get(reverse('register'), HTTP_ACCEPT_LANGUAGE='en')

        self.assertContains(english_login, 'data-loading-label="Signing in..."')
        self.assertContains(english_register, 'data-loading-label="Creating account..."')
