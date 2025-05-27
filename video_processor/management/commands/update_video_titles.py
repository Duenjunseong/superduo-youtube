from django.core.management.base import BaseCommand
from video_processor.models import ProcessingJob
from video_processor.utils import get_youtube_video_title


class Command(BaseCommand):
    help = '기존 작업들의 YouTube 비디오 제목을 업데이트합니다.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='이미 제목이 있는 작업도 다시 업데이트합니다.',
        )

    def handle(self, *args, **options):
        force_update = options['force']
        
        if force_update:
            jobs = ProcessingJob.objects.all()
            self.stdout.write('모든 작업의 제목을 업데이트합니다...')
        else:
            jobs = ProcessingJob.objects.filter(video_title__isnull=True) | ProcessingJob.objects.filter(video_title='')
            self.stdout.write('제목이 없는 작업들의 제목을 업데이트합니다...')
        
        total_jobs = jobs.count()
        if total_jobs == 0:
            self.stdout.write(self.style.SUCCESS('업데이트할 작업이 없습니다.'))
            return
        
        self.stdout.write(f'총 {total_jobs}개의 작업을 처리합니다.')
        
        updated_count = 0
        failed_count = 0
        
        for job in jobs:
            try:
                old_title = job.video_title
                new_title = get_youtube_video_title(job.youtube_url)
                
                if new_title != '제목 미탐지':
                    job.video_title = new_title
                    job.save(update_fields=['video_title'])
                    updated_count += 1
                    
                    if old_title != new_title:
                        self.stdout.write(f'✓ {job.job_id}: "{new_title}"')
                    else:
                        self.stdout.write(f'- {job.job_id}: 제목 변경 없음')
                else:
                    failed_count += 1
                    self.stdout.write(f'✗ {job.job_id}: 제목 가져오기 실패')
                    
            except Exception as e:
                failed_count += 1
                self.stdout.write(f'✗ {job.job_id}: 오류 - {str(e)}')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n완료: {updated_count}개 업데이트, {failed_count}개 실패'
            )
        ) 