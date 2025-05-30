from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from workspace.models import Workspace, WorkspaceMembership

User = get_user_model()

class Command(BaseCommand):
    help = '샘플 워크스페이스와 멤버십을 생성합니다'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='워크스페이스를 생성할 사용자의 username',
            default='admin'
        )

    def handle(self, *args, **options):
        username = options['username']
        
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'사용자 "{username}"을 찾을 수 없습니다.')
            )
            return

        # 샘플 워크스페이스 생성
        workspaces_data = [
            {
                'name': '마케팅팀',
                'description': '마케팅 콘텐츠 제작 및 관리',
                'is_public': False,
                'max_members': 15
            },
            {
                'name': '개발팀',
                'description': '개발 관련 영상 및 문서',
                'is_public': False,
                'max_members': 10
            },
            {
                'name': 'YouTube 채널',
                'description': 'YouTube 콘텐츠 제작 및 편집',
                'is_public': True,
                'max_members': 20
            }
        ]

        created_workspaces = []
        
        for ws_data in workspaces_data:
            workspace, created = Workspace.objects.get_or_create(
                name=ws_data['name'],
                defaults={
                    'description': ws_data['description'],
                    'is_public': ws_data['is_public'],
                    'max_members': ws_data['max_members'],
                    'owner': user,
                    'status': 'ACTIVE'
                }
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'워크스페이스 "{workspace.name}" 생성됨')
                )
                
                # 소유자를 ADMIN 멤버로 추가
                membership, membership_created = WorkspaceMembership.objects.get_or_create(
                    workspace=workspace,
                    user=user,
                    defaults={
                        'role': 'ADMIN',
                        'status': 'ACTIVE'
                    }
                )
                
                if membership_created:
                    self.stdout.write(
                        self.style.SUCCESS(f'  - "{user.username}" ADMIN 멤버십 생성됨')
                    )
                    
                created_workspaces.append(workspace)
            else:
                self.stdout.write(
                    self.style.WARNING(f'워크스페이스 "{workspace.name}" 이미 존재함')
                )

        if created_workspaces:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n총 {len(created_workspaces)}개의 워크스페이스가 생성되었습니다.'
                )
            )
            
            # 첫 번째 워크스페이스를 현재 워크스페이스로 설정
            if not user.current_workspace and created_workspaces:
                user.current_workspace = created_workspaces[0]
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        f'"{created_workspaces[0].name}"을 현재 워크스페이스로 설정했습니다.'
                    )
                )
        else:
            self.stdout.write(
                self.style.WARNING('새로 생성된 워크스페이스가 없습니다.')
            ) 