from django.core.management.base import BaseCommand
from django.conf import settings
from downloads.models import File
import os
from pathlib import Path


class Command(BaseCommand):
    help = '기존 파일들의 절대 경로를 상대 경로로 변환합니다.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='실제로 변경하지 않고 변경될 내용만 출력합니다.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        media_root = Path(settings.MEDIA_ROOT)
        
        self.stdout.write(f"MEDIA_ROOT: {media_root}")
        
        files_to_update = []
        files = File.objects.all()
        
        for file in files:
            file_path = Path(file.file_path)
            
            # 절대 경로인 경우 상대 경로로 변환
            if file_path.is_absolute():
                try:
                    # MEDIA_ROOT에 대한 상대 경로 계산
                    relative_path = file_path.relative_to(media_root)
                    files_to_update.append((file, str(relative_path)))
                    
                    self.stdout.write(
                        f"파일 {file.id}:"
                    )
                    self.stdout.write(f"  현재 경로: {file.file_path}")
                    self.stdout.write(f"  새 경로: {relative_path}")
                    self.stdout.write(f"  파일 존재: {file_path.exists()}")
                    
                except ValueError:
                    # MEDIA_ROOT 밖에 있는 파일
                    self.stdout.write(
                        self.style.WARNING(
                            f"파일 {file.id}가 MEDIA_ROOT 밖에 있습니다: {file.file_path}"
                        )
                    )
            else:
                # 이미 상대 경로인 경우 파일 존재 여부만 확인
                full_path = media_root / file.file_path
                self.stdout.write(
                    f"파일 {file.id} (상대경로): {file.file_path} - 존재: {full_path.exists()}"
                )
        
        if files_to_update:
            if dry_run:
                self.stdout.write(
                    self.style.SUCCESS(f"총 {len(files_to_update)}개의 파일이 변경될 예정입니다. (실제 변경되지 않음)")
                )
            else:
                # 실제 업데이트 수행
                updated_count = 0
                for file, new_path in files_to_update:
                    file.file_path = new_path
                    file.save()
                    updated_count += 1
                
                self.stdout.write(
                    self.style.SUCCESS(f"총 {updated_count}개의 파일 경로가 업데이트되었습니다.")
                )
        else:
            self.stdout.write(
                self.style.SUCCESS("업데이트할 파일이 없습니다.")
            ) 