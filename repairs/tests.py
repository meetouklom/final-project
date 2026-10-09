from django.test import TestCase
from django.urls import reverse
from django.db import connection
from django.utils import timezone
from unittest.mock import patch
from accounts.models import User
from .models import Notification, RepairComment, RepairRequest


class RepairAIAnalysisTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            username='student',
            password='pass-1234',
            role=User.Role.STUDENT,
            room_number='A-101',
        )
        self.supervisor = User.objects.create_user(
            username='supervisor',
            password='pass-1234',
            role=User.Role.SUPERVISOR,
        )
        self.repair = RepairRequest.objects.create(
            reported_by=self.student,
            title='Water leaking',
            category=RepairRequest.Category.OTHER,
            location='A-101',
            description='Water is leaking under the sink.',
        )
        self.analysis = {
            'summary_th': 'น้ำรั่วใต้ซิงก์',
            'summary_en': 'Water leaking under the sink.',
            'category': RepairRequest.Category.PLUMBING,
            'urgency': RepairRequest.AIUrgency.NORMAL,
            'reason_th': 'ท่อใต้ซิงก์รั่ว เป็นปัญหาระบบประปา',
            'reason_en': 'A sink leak is a plumbing issue.',
        }

    def test_database_defaults_allow_insert_without_ai_columns(self):
        now = timezone.now().isoformat()
        with connection.cursor() as cursor:
            cursor.execute(
                '''
                INSERT INTO repairs_repairrequest
                    (reported_by_id, title, description, category, location, status,
                     supervisor_note, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''',
                [
                    self.student.pk,
                    'Legacy request',
                    'Request created by an app instance without AI fields.',
                    RepairRequest.Category.OTHER,
                    'A-101',
                    RepairRequest.Status.RECEIVED,
                    '',
                    now,
                    now,
                ],
            )
            repair_id = cursor.lastrowid

        repair = RepairRequest.objects.get(pk=repair_id)
        self.assertEqual(repair.ai_summary, '')
        self.assertEqual(repair.ai_suggested_category, '')
        self.assertEqual(repair.ai_urgency, '')
        self.assertEqual(repair.ai_reason, '')

    def test_ai_action_is_prominent_at_the_top_of_supervisor_detail(self):
        self.client.force_login(self.supervisor)

        response = self.client.get(reverse('repair_detail', args=[self.repair.pk]))

        self.assertContains(response, 'id="ai-analysis"')
        self.assertContains(response, 'กดที่นี่เพื่อวิเคราะห์ด้วย AI')
        self.assertLess(
            response.content.index(b'id="ai-analysis"'),
            response.content.index(b'class="repair-stepper"'),
        )

    def test_supervisor_dashboard_has_an_ai_button_for_each_request(self):
        self.client.force_login(self.supervisor)

        response = self.client.get(reverse('dashboard'))

        self.assertContains(response, reverse('repair_ai_analyze', args=[self.repair.pk]))
        self.assertContains(response, 'วิเคราะห์ AI')

    def test_resident_dashboard_does_not_show_supervisor_ai_actions(self):
        self.client.force_login(self.student)

        response = self.client.get(reverse('dashboard'))

        self.assertNotContains(response, 'วิเคราะห์ AI')

    @patch('repairs.views.analyze_repair_request')
    def test_supervisor_can_save_ai_suggestions_without_changing_request(self, analyze):
        analyze.return_value = self.analysis
        self.client.force_login(self.supervisor)

        response = self.client.post(reverse('repair_ai_analyze', args=[self.repair.pk]))

        self.assertRedirects(response, reverse('repair_detail', args=[self.repair.pk]))
        self.repair.refresh_from_db()
        self.assertEqual(self.repair.ai_summary_th, self.analysis['summary_th'])
        self.assertEqual(self.repair.ai_summary_en, self.analysis['summary_en'])
        self.assertEqual(self.repair.ai_reason_th, self.analysis['reason_th'])
        self.assertEqual(self.repair.ai_reason_en, self.analysis['reason_en'])
        self.assertEqual(self.repair.ai_suggested_category, RepairRequest.Category.PLUMBING)
        self.assertEqual(self.repair.ai_urgency, RepairRequest.AIUrgency.NORMAL)
        self.assertTrue(self.repair.ai_analyzed_at)
        self.assertEqual(self.repair.category, RepairRequest.Category.OTHER)
        self.assertEqual(self.repair.status, RepairRequest.Status.RECEIVED)
        self.assertContains(
            self.client.get(reverse('repair_detail', args=[self.repair.pk])),
            self.analysis['summary_th'],
        )

    @patch('repairs.views.analyze_repair_request')
    def test_ai_results_follow_the_selected_page_language(self, analyze):
        analyze.return_value = self.analysis
        self.client.force_login(self.supervisor)
        detail_url = reverse('repair_detail', args=[self.repair.pk])

        self.client.post(reverse('set_language'), {'language': 'th', 'next': detail_url})
        self.client.post(reverse('repair_ai_analyze', args=[self.repair.pk]))
        thai_response = self.client.get(detail_url)
        self.assertContains(thai_response, self.analysis['summary_th'])
        self.assertContains(thai_response, self.analysis['reason_th'])
        self.assertNotContains(thai_response, self.analysis['summary_en'])

        self.client.post(reverse('set_language'), {'language': 'en', 'next': detail_url})
        english_response = self.client.get(detail_url)
        self.assertContains(english_response, self.analysis['summary_en'])
        self.assertContains(english_response, self.analysis['reason_en'])
        self.assertNotContains(english_response, self.analysis['summary_th'])

    @patch('repairs.views.analyze_repair_request')
    def test_resident_cannot_request_ai_analysis(self, analyze):
        self.client.force_login(self.student)

        response = self.client.post(reverse('repair_ai_analyze', args=[self.repair.pk]))

        self.assertEqual(response.status_code, 403)
        analyze.assert_not_called()
        detail_response = self.client.get(reverse('repair_detail', args=[self.repair.pk]))
        self.assertNotContains(detail_response, 'LOCAL AI ASSISTANT')

    @patch('repairs.views.analyze_repair_request')
    def test_ai_connection_failure_is_reported_without_saving_suggestions(self, analyze):
        from .ai import AIAnalysisError

        analyze.side_effect = AIAnalysisError('Could not connect to Ollama. Start Ollama and try again.')
        self.client.force_login(self.supervisor)

        response = self.client.post(reverse('repair_ai_analyze', args=[self.repair.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('repair_detail', args=[self.repair.pk]))
        self.assertIn('Ollama', str(list(response.wsgi_request._messages)[0]))
        self.repair.refresh_from_db()
        self.assertFalse(self.repair.ai_analyzed_at)


class RepairFlowTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(username='student', password='pass-1234', role=User.Role.STUDENT, room_number='A-101')
        self.supervisor = User.objects.create_user(username='supervisor', password='pass-1234', role=User.Role.SUPERVISOR)

    def test_student_can_create_and_see_own_request(self):
        self.client.force_login(self.student)
        response = self.client.post(reverse('repair_create'), {'title': 'Broken light', 'category': 'electricity', 'location': 'A-101', 'description': 'Ceiling light is out.'})
        self.assertRedirects(response, reverse('dashboard'))
        self.assertEqual(RepairRequest.objects.count(), 1)
        self.assertContains(self.client.get(reverse('dashboard')), 'Broken light')

    def test_new_requests_have_blank_ai_suggestions_by_default(self):
        repair = RepairRequest.objects.create(
            reported_by=self.student,
            title='Broken light',
            category=RepairRequest.Category.ELECTRICITY,
            location='A-101',
            description='Ceiling light is out.',
        )

        self.assertEqual(repair.ai_summary, '')
        self.assertEqual(repair.ai_suggested_category, '')
        self.assertEqual(repair.ai_urgency, '')
        self.assertEqual(repair.ai_reason, '')

    def test_student_cannot_access_another_students_request(self):
        other = User.objects.create_user(username='other', password='pass-1234', room_number='B-202')
        repair = RepairRequest.objects.create(reported_by=other, title='Private issue', category='other', location='B-202', description='Private')
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse('repair_detail', args=[repair.pk])).status_code, 403)

    def test_repair_detail_localizes_metadata_and_highlights_dashboard_navigation(self):
        repair = RepairRequest.objects.create(
            reported_by=self.student,
            title='Broken light',
            category=RepairRequest.Category.ELECTRICITY,
            location='A-101',
            description='Ceiling light is out.',
        )
        self.client.force_login(self.student)

        response = self.client.get(reverse('repair_detail', args=[repair.pk]))

        self.assertContains(response, 'Broken light')
        self.assertContains(response, 'ไฟฟ้า')
        self.assertContains(response, 'รับแจ้งแล้ว')
        self.assertContains(response, 'class="repair-stepper"')
        self.assertContains(response, 'อัปเดตและความคิดเห็น')
        self.assertContains(response, 'ส่งความคิดเห็น')
        self.assertNotContains(response, 'repair-rating-card')
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(response, 'data-delete-dialog')
        self.assertNotContains(response, 'รรรร')

        self.client.post(reverse('set_language'), {'language': 'en', 'next': reverse('repair_detail', args=[repair.pk])})
        response = self.client.get(reverse('repair_detail', args=[repair.pk]))

        self.assertContains(response, 'Electricity')
        self.assertContains(response, 'Received')
        self.assertContains(response, 'Problem details')
        self.assertContains(response, 'Updates & comments')
        self.assertContains(response, 'Keep request')
        self.assertNotContains(response, 'ไฟฟ้า')

    def test_repair_comments_are_shared_with_supervisor_and_resident_in_order(self):
        repair = RepairRequest.objects.create(
            reported_by=self.student,
            title='Broken light',
            category=RepairRequest.Category.ELECTRICITY,
            location='A-101',
            description='Ceiling light is out.',
        )
        self.client.force_login(self.student)
        response = self.client.post(
            reverse('repair_comment', args=[repair.pk]),
            {'body': 'I can be home after 5.'},
        )
        self.assertRedirects(response, reverse('repair_detail', args=[repair.pk]))
        self.assertEqual(RepairComment.objects.count(), 1)

        self.client.force_login(self.supervisor)
        response = self.client.post(
            reverse('repair_comment', args=[repair.pk]),
            {'body': 'A technician will visit tomorrow.'},
        )
        self.assertRedirects(response, reverse('repair_detail', args=[repair.pk]))
        response = self.client.get(reverse('repair_detail', args=[repair.pk]))
        self.assertContains(response, 'I can be home after 5.')
        self.assertContains(response, 'A technician will visit tomorrow.')
        self.assertLess(
            response.content.index(b'I can be home after 5.'),
            response.content.index(b'A technician will visit tomorrow.'),
        )

    def test_supervisor_comment_inbox_shows_all_discussions_and_can_search_comments(self):
        first_repair = RepairRequest.objects.create(
            reported_by=self.student,
            title='Broken light',
            category=RepairRequest.Category.ELECTRICITY,
            location='A-101',
            description='Ceiling light is out.',
        )
        other_student = User.objects.create_user(
            username='other-student',
            password='pass-1234',
            room_number='B-202',
        )
        second_repair = RepairRequest.objects.create(
            reported_by=other_student,
            title='Leaking tap',
            category=RepairRequest.Category.PLUMBING,
            location='B-202',
            description='Tap leaks.',
        )
        RepairComment.objects.create(
            repair=first_repair,
            author=self.student,
            body='Please visit after 5.',
        )
        RepairComment.objects.create(
            repair=second_repair,
            author=other_student,
            body='The water is getting worse.',
        )
        self.client.force_login(self.supervisor)

        response = self.client.get(reverse('comment_management'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Broken light')
        self.assertContains(response, 'Leaking tap')
        self.assertContains(response, 'Please visit after 5.')
        self.assertContains(response, reverse('comment_management_reply', args=[first_repair.pk]))
        self.assertEqual(len(response.context['discussions']), 2)
        navigation = response.content.split(b'<nav class="sidebar-nav"', 1)[1].split(b'</nav>', 1)[0]
        self.assertLess(navigation.index(b'href="/dashboard/"'), navigation.index(b'href="/repairs/new/"'))
        self.assertNotIn(b'href="/features/"', navigation)
        self.assertNotIn(b'>Home<', navigation)
        self.assertNotIn(b'>Features<', navigation)
        self.assertLess(navigation.index(b'href="/repairs/new/"'), navigation.index(b'href="/repairs/comments/"'))
        self.assertLess(navigation.index(b'href="/repairs/comments/"'), navigation.index(b'href="/account-management/"'))
        self.assertContains(response, 'aria-current="page"')

        search_response = self.client.get(reverse('comment_management'), {'q': 'water is getting'})
        self.assertEqual(len(search_response.context['discussions']), 1)
        self.assertEqual(search_response.context['discussions'][0], second_repair)

    def test_only_supervisors_can_access_comment_inbox_or_reply(self):
        repair = RepairRequest.objects.create(
            reported_by=self.student,
            title='Broken light',
            category=RepairRequest.Category.ELECTRICITY,
            location='A-101',
            description='Ceiling light is out.',
        )
        self.client.force_login(self.student)

        inbox_response = self.client.get(reverse('comment_management'))
        reply_response = self.client.post(
            reverse('comment_management_reply', args=[repair.pk]),
            {'body': 'A technician is on the way.'},
        )

        self.assertEqual(inbox_response.status_code, 403)
        self.assertEqual(reply_response.status_code, 403)
        self.assertFalse(RepairComment.objects.exists())

    def test_supervisor_can_reply_from_comment_inbox_and_notifies_reporter(self):
        repair = RepairRequest.objects.create(
            reported_by=self.student,
            title='Broken light',
            category=RepairRequest.Category.ELECTRICITY,
            location='A-101',
            description='Ceiling light is out.',
        )
        self.client.force_login(self.supervisor)

        response = self.client.post(
            reverse('comment_management_reply', args=[repair.pk]),
            {'body': 'A technician will visit tomorrow.'},
        )

        self.assertRedirects(
            response,
            f"{reverse('comment_management')}#discussion-{repair.pk}",
        )
        reply = RepairComment.objects.get(repair=repair)
        self.assertEqual(reply.author, self.supervisor)
        self.assertEqual(reply.body, 'A technician will visit tomorrow.')
        self.assertTrue(Notification.objects.filter(
            user=self.student,
            type=Notification.Type.COMMENT,
            reference=repair,
            message__contains='A technician will visit tomorrow.',
        ).exists())

    def test_new_repair_notifies_active_supervisors(self):
        self.client.force_login(self.student)
        response = self.client.post(reverse('repair_create'), {
            'title': 'Broken light',
            'category': 'electricity',
            'location': 'A-101',
            'description': 'Ceiling light is out.',
        })

        self.assertEqual(response.status_code, 302)
        notification = Notification.objects.get(user=self.supervisor)
        self.assertEqual(notification.type, Notification.Type.NEW_REPAIR)
        self.assertEqual(notification.reference.title, 'Broken light')

    def test_repair_api_creation_notifies_supervisors(self):
        self.client.force_login(self.student)
        response = self.client.post(
            reverse('api-repair-list'),
            data='{"title":"Broken light","category":"electricity","location":"B-202","description":"Ceiling light is out."}',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['location'], 'A-101')
        self.assertTrue(Notification.objects.filter(
            user=self.supervisor,
            type=Notification.Type.NEW_REPAIR,
            reference_id=response.json()['id'],
        ).exists())

    def test_status_change_notifies_the_reporter_only_when_status_changes(self):
        repair = RepairRequest.objects.create(
            reported_by=self.student,
            title='Broken tap',
            category='plumbing',
            location='A-101',
            description='Tap leaks.',
        )
        self.client.force_login(self.supervisor)

        self.client.post(reverse('repair_update', args=[repair.pk]), {
            'status': RepairRequest.Status.IN_PROGRESS,
            'supervisor_note': '',
            'assigned_to': '',
        })
        notification = Notification.objects.get(user=self.student)
        self.assertEqual(notification.type, Notification.Type.STATUS_CHANGE)
        self.assertEqual(notification.reference_id, repair.pk)

        self.client.post(reverse('repair_update', args=[repair.pk]), {
            'status': RepairRequest.Status.IN_PROGRESS,
            'supervisor_note': '',
            'assigned_to': '',
        })
        self.assertEqual(Notification.objects.filter(user=self.student).count(), 1)

    def test_new_comment_notifies_the_other_side_of_the_repair(self):
        repair = RepairRequest.objects.create(
            reported_by=self.student,
            title='Broken light',
            category='electricity',
            location='A-101',
            description='Ceiling light is out.',
        )
        self.client.force_login(self.student)
        self.client.post(reverse('repair_comment', args=[repair.pk]), {'body': 'Any update?'})

        notification = Notification.objects.get(user=self.supervisor)
        self.assertEqual(notification.type, Notification.Type.COMMENT)
        self.assertIn('Any update?', notification.message)

        self.client.force_login(self.supervisor)
        self.client.post(reverse('repair_comment', args=[repair.pk]), {'body': 'Technician assigned.'})
        self.assertEqual(Notification.objects.filter(user=self.student, type=Notification.Type.COMMENT).count(), 1)

    def test_notifications_api_lists_and_marks_only_the_current_users_notifications(self):
        repair = RepairRequest.objects.create(
            reported_by=self.student,
            title='Broken light',
            category=RepairRequest.Category.ELECTRICITY,
            location='A-101',
            description='Ceiling light is out.',
            status=RepairRequest.Status.IN_PROGRESS,
        )
        own = Notification.objects.create(
            user=self.student,
            title='Repair updated',
            message='In progress',
            type=Notification.Type.STATUS_CHANGE,
            reference=repair,
        )
        other = User.objects.create_user(username='other', password='pass-1234')
        private = Notification.objects.create(
            user=other,
            title='Private',
            message='Private notification',
            type=Notification.Type.COMMENT,
        )
        self.client.force_login(self.student)

        response = self.client.get('/api/notifications/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['unread_count'], 1)
        self.assertEqual(response.json()['results'][0]['id'], own.pk)
        self.assertEqual(response.json()['results'][0]['reference_status'], RepairRequest.Status.IN_PROGRESS)
        self.assertEqual(self.client.post(reverse('api-notification-read', args=[private.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('api-notification-read', args=[own.pk])).status_code, 200)
        self.assertTrue(Notification.objects.get(pk=own.pk).is_read)

        second = Notification.objects.create(
            user=self.student,
            title='Another update',
            message='Waiting for parts',
            type=Notification.Type.STATUS_CHANGE,
        )
        self.client.post(reverse('api-notifications-read-all'))
        self.assertTrue(Notification.objects.get(pk=second.pk).is_read)

    def test_notification_dropdown_is_rendered_for_authenticated_users(self):
        self.client.force_login(self.student)

        response = self.client.get(reverse('dashboard'))

        self.assertContains(response, 'data-notification-center')
        self.assertContains(response, 'data-list-url="/api/notifications/"')
        self.assertContains(response, 'data-notification-count')
        self.assertContains(response, 'notification-bell-icon')
        self.assertContains(response, 'data-mark-all-notifications')

    def test_dashboard_renders_request_search_and_clear_filters(self):
        RepairRequest.objects.create(
            reported_by=self.student,
            title='Broken light',
            category=RepairRequest.Category.ELECTRICITY,
            location='A-101',
            description='Ceiling light is out.',
        )
        self.client.force_login(self.student)

        response = self.client.get(reverse('dashboard'))

        self.assertContains(response, 'data-request-search')
        self.assertContains(response, 'data-request-status-filter')
        self.assertContains(response, 'data-clear-request-filters')
        self.assertContains(response, 'data-request-row')
        self.assertContains(response, 'data-request-status="received"')

    def test_repair_api_status_update_notifies_reporter_and_residents_cannot_change_status(self):
        repair = RepairRequest.objects.create(
            reported_by=self.student,
            title='Broken tap',
            category='plumbing',
            location='A-101',
            description='Tap leaks.',
        )
        self.client.force_login(self.supervisor)
        response = self.client.patch(
            reverse('api-repair-detail', args=[repair.pk]),
            data='{"status":"waiting"}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Notification.objects.get(user=self.student).type,
            Notification.Type.STATUS_CHANGE,
        )

        repair.status = RepairRequest.Status.IN_PROGRESS
        repair.save(update_fields=('status',))
        self.client.force_login(self.student)
        response = self.client.patch(
            reverse('api-repair-detail', args=[repair.pk]),
            data='{"status":"completed"}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_other_resident_cannot_read_or_post_repair_comments(self):
        repair = RepairRequest.objects.create(
            reported_by=self.student,
            title='Broken light',
            category=RepairRequest.Category.ELECTRICITY,
            location='A-101',
            description='Ceiling light is out.',
        )
        other = User.objects.create_user(username='other', password='pass-1234')
        self.client.force_login(other)

        self.assertEqual(self.client.get(reverse('repair_detail', args=[repair.pk])).status_code, 403)
        self.assertEqual(
            self.client.post(reverse('repair_comment', args=[repair.pk]), {'body': 'Private comment'}).status_code,
            403,
        )
        self.assertEqual(RepairComment.objects.count(), 0)

    def test_completed_repair_can_be_rated_once_by_reporting_resident(self):
        repair = RepairRequest.objects.create(
            reported_by=self.student,
            title='Broken light',
            category=RepairRequest.Category.ELECTRICITY,
            location='A-101',
            description='Ceiling light is out.',
            status=RepairRequest.Status.COMPLETED,
        )
        self.client.force_login(self.student)
        self.client.post(reverse('set_language'), {'language': 'en', 'next': reverse('repair_detail', args=[repair.pk])})
        response = self.client.get(reverse('repair_detail', args=[repair.pk]))
        self.assertContains(response, 'repair-rating-card')
        self.assertContains(response, 'name="rating"')
        self.assertContains(response, 'Your rating')

        response = self.client.post(reverse('repair_rating', args=[repair.pk]), {'rating': '5'})
        self.assertRedirects(response, reverse('repair_detail', args=[repair.pk]))
        repair.refresh_from_db()
        self.assertEqual(repair.rating, 5)
        self.assertContains(self.client.get(reverse('repair_detail', args=[repair.pk])), 'Rated 5 out of 5 stars')

        self.assertEqual(
            self.client.post(reverse('repair_rating', args=[repair.pk]), {'rating': '4'}).status_code,
            403,
        )
        repair.refresh_from_db()
        self.assertEqual(repair.rating, 5)

    def test_repair_rating_is_only_available_after_completion_and_by_reporter(self):
        repair = RepairRequest.objects.create(
            reported_by=self.student,
            title='Broken light',
            category=RepairRequest.Category.ELECTRICITY,
            location='A-101',
            description='Ceiling light is out.',
        )
        self.client.force_login(self.student)
        self.assertEqual(
            self.client.post(reverse('repair_rating', args=[repair.pk]), {'rating': '5'}).status_code,
            403,
        )

        repair.status = RepairRequest.Status.COMPLETED
        repair.save(update_fields=('status',))
        self.client.force_login(self.supervisor)
        self.assertEqual(
            self.client.post(reverse('repair_rating', args=[repair.pk]), {'rating': '5'}).status_code,
            403,
        )

    def test_supervisor_update_form_localizes_labels_and_status_choices(self):
        repair = RepairRequest.objects.create(
            reported_by=self.student,
            title='Broken tap',
            category=RepairRequest.Category.PLUMBING,
            location='A-101',
            description='Tap is leaking.',
        )
        self.client.force_login(self.supervisor)

        response = self.client.get(reverse('repair_detail', args=[repair.pk]))

        self.assertContains(response, 'จัดการรายการ')
        self.assertContains(response, 'รออะไหล่')

        self.client.post(reverse('set_language'), {'language': 'en', 'next': reverse('repair_detail', args=[repair.pk])})
        response = self.client.get(reverse('repair_detail', args=[repair.pk]))

        self.assertContains(response, 'Manage request')
        self.assertContains(response, 'Waiting for parts')
        self.assertNotContains(response, 'หมายเหตุจากผู้ดูแล')

    def test_supervisor_can_update_status(self):
        repair = RepairRequest.objects.create(reported_by=self.student, title='Broken tap', category='plumbing', location='A-101', description='Tap leaks')
        self.client.force_login(self.supervisor)
        response = self.client.post(reverse('repair_update', args=[repair.pk]), {'status': 'completed', 'supervisor_note': 'Fixed.', 'assigned_to': self.supervisor.pk})
        self.assertRedirects(response, reverse('repair_detail', args=[repair.pk]))
        repair.refresh_from_db()
        self.assertEqual(repair.status, RepairRequest.Status.COMPLETED)

    def test_login_page_switches_to_english_without_mixed_language_text(self):
        self.client.post(reverse('set_language'), {'language': 'en', 'next': '/login/'})
        response = self.client.get(reverse('login'))
        content = response.content.decode('utf-8')
        self.assertContains(response, 'Sign in')
        self.assertNotIn('เข้าสู่ระบบ', content)
        self.assertNotIn('แจ้งปัญหาภายในหอพัก', content)

    def test_repair_form_uses_registered_room_number_as_default_location(self):
        self.student.room_number = 'A-101'
        self.student.save()
        self.client.force_login(self.student)

        response = self.client.get(reverse('repair_create'))

        self.assertContains(response, 'value="A-101"')
        self.assertContains(response, 'disabled')
        self.assertContains(response, 'บันทึกไว้ในบัญชีของคุณ')

    def test_repair_request_uses_account_room_even_if_posted_location_is_tampered(self):
        self.client.force_login(self.student)

        response = self.client.post(reverse('repair_create'), {
            'title': 'Broken light',
            'category': 'electricity',
            'location': 'B-202',
            'description': 'Ceiling light is out.',
        })

        self.assertRedirects(response, reverse('dashboard'))
        repair = RepairRequest.objects.get()
        self.assertEqual(repair.location, self.student.room_number)

    def test_repair_form_localizes_fields_and_renders_dropzone(self):
        self.client.force_login(self.student)

        response = self.client.get(reverse('repair_create'))

        self.assertContains(response, 'ลากรูปภาพมาวางที่นี่')
        self.assertContains(response, 'หมวดหมู่')
        self.assertContains(response, 'เลือกหมวดหมู่')
        self.assertContains(response, 'data-file-dropzone')
        self.assertContains(response, 'data-file-preview')
        self.assertContains(response, 'data-remove-image')
        self.assertContains(response, 'ลากรูปภาพมาวางที่นี่')
        self.assertContains(response, 'WebP')

        self.client.post(reverse('set_language'), {'language': 'en', 'next': reverse('repair_create')})
        response = self.client.get(reverse('repair_create'))

        self.assertContains(response, 'Drag and drop your image here')
        self.assertContains(response, 'Issue title')
        self.assertContains(response, 'Choose a category')
        self.assertNotContains(response, 'ลากรูปภาพมาวางที่นี่')
