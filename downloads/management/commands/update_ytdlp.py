from django.core.management.base import BaseCommand
import subprocess
import sys


class Command(BaseCommand):
    help = 'yt-dlp를 최신 버전으로 업데이트합니다'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='강제로 재설치합니다',
        )

    def handle(self, *args, **options):
        try:
            # 현재 버전 확인
            try:
                result = subprocess.run(['yt-dlp', '--version'], capture_output=True, text=True, check=True)
                current_version = result.stdout.strip()
                self.stdout.write(f"현재 yt-dlp 버전: {current_version}")
            except FileNotFoundError:
                self.stdout.write(self.style.WARNING("yt-dlp가 설치되지 않았습니다."))
                current_version = None
            except subprocess.CalledProcessError:
                self.stdout.write(self.style.WARNING("yt-dlp 버전을 확인할 수 없습니다."))
                current_version = None

            # 업데이트 또는 설치
            if options['force'] or current_version is None:
                self.stdout.write("yt-dlp를 설치/업데이트합니다...")
                cmd = [sys.executable, '-m', 'pip', 'install', '--upgrade', 'yt-dlp']
            else:
                self.stdout.write("yt-dlp를 업데이트합니다...")
                cmd = [sys.executable, '-m', 'pip', 'install', '--upgrade', 'yt-dlp']

            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            
            # 업데이트 후 버전 확인
            result = subprocess.run(['yt-dlp', '--version'], capture_output=True, text=True, check=True)
            new_version = result.stdout.strip()
            
            if current_version != new_version:
                self.stdout.write(
                    self.style.SUCCESS(f"yt-dlp가 성공적으로 업데이트되었습니다: {new_version}")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f"yt-dlp는 이미 최신 버전입니다: {new_version}")
                )

        except subprocess.CalledProcessError as e:
            self.stdout.write(
                self.style.ERROR(f"yt-dlp 업데이트 실패: {e}")
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"예상치 못한 오류: {e}")
            ) 