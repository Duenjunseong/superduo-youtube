from django.core.management.base import BaseCommand
import subprocess
import tempfile
import os
import json


class Command(BaseCommand):
    help = 'yt-dlp 다운로드 기능을 테스트합니다'

    def add_arguments(self, parser):
        parser.add_argument(
            'url',
            type=str,
            help='테스트할 YouTube URL',
        )
        parser.add_argument(
            '--info-only',
            action='store_true',
            help='비디오 정보만 가져옵니다 (다운로드하지 않음)',
        )

    def handle(self, *args, **options):
        url = options['url']
        
        try:
            # yt-dlp 버전 확인
            result = subprocess.run(['yt-dlp', '--version'], capture_output=True, text=True, check=True)
            self.stdout.write(f"yt-dlp 버전: {result.stdout.strip()}")
            
            if options['info_only']:
                # 비디오 정보만 가져오기
                self.stdout.write("비디오 정보를 가져오는 중...")
                cmd = [
                    'yt-dlp',
                    '--dump-json',
                    '--no-playlist',
                    '--no-warnings',
                    url
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                video_info = json.loads(result.stdout)
                
                self.stdout.write(self.style.SUCCESS("비디오 정보:"))
                self.stdout.write(f"  제목: {video_info.get('title', 'N/A')}")
                self.stdout.write(f"  ID: {video_info.get('id', 'N/A')}")
                self.stdout.write(f"  길이: {video_info.get('duration', 'N/A')}초")
                self.stdout.write(f"  업로더: {video_info.get('uploader', 'N/A')}")
                self.stdout.write(f"  조회수: {video_info.get('view_count', 'N/A')}")
            else:
                # 실제 다운로드 테스트
                with tempfile.TemporaryDirectory() as temp_dir:
                    self.stdout.write("테스트 다운로드를 시작합니다...")
                    
                    output_template = os.path.join(temp_dir, '%(id)s.%(ext)s')
                    
                    # YouTube Shorts 확인
                    is_shorts = 'shorts/' in url.lower()
                    if is_shorts:
                        self.stdout.write("YouTube Shorts 감지됨")
                    
                    cmd = [
                        'yt-dlp',
                        '-f', 'best[height<=480]',  # 테스트용으로 낮은 품질
                        '--no-playlist',
                        '--no-warnings',
                        '--no-check-certificate',
                        '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        '-o', output_template,
                        url
                    ]
                    
                    if is_shorts:
                        cmd.extend(['--extractor-args', 'youtube:player_client=android'])
                    
                    self.stdout.write(f"실행 명령: {' '.join(cmd)}")
                    
                    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                    
                    # 다운로드된 파일 확인
                    downloaded_files = [f for f in os.listdir(temp_dir) if os.path.isfile(os.path.join(temp_dir, f))]
                    
                    if downloaded_files:
                        file_path = os.path.join(temp_dir, downloaded_files[0])
                        file_size = os.path.getsize(file_path)
                        self.stdout.write(self.style.SUCCESS(f"다운로드 성공!"))
                        self.stdout.write(f"  파일명: {downloaded_files[0]}")
                        self.stdout.write(f"  파일 크기: {file_size:,} bytes")
                    else:
                        self.stdout.write(self.style.ERROR("다운로드된 파일을 찾을 수 없습니다."))

        except FileNotFoundError:
            self.stdout.write(self.style.ERROR("yt-dlp가 설치되지 않았습니다. 'python manage.py update_ytdlp' 명령을 실행해주세요."))
        except subprocess.CalledProcessError as e:
            self.stdout.write(self.style.ERROR(f"yt-dlp 실행 실패:"))
            self.stdout.write(f"Exit code: {e.returncode}")
            self.stdout.write(f"stdout: {e.stdout}")
            self.stdout.write(f"stderr: {e.stderr}")
        except json.JSONDecodeError as e:
            self.stdout.write(self.style.ERROR(f"JSON 파싱 오류: {e}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"예상치 못한 오류: {e}")) 