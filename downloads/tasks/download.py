import os
import tempfile
import subprocess
from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
import time
import random
import logging
import json
import sys
import shutil

# 로거 설정
logger = logging.getLogger(__name__)

# 모델 임포트
from downloads.models import Job, File

# User 모델 가져오기
User = get_user_model()

def ensure_yt_dlp():
    """yt-dlp 설치 및 업데이트 확인"""
    try:
        # yt-dlp 버전 확인
        version_result = subprocess.run(['yt-dlp', '--version'], capture_output=True, text=True, check=True)
        current_version = version_result.stdout.strip()
        logger.info(f"현재 yt-dlp 버전: {current_version}")
        return True
    except FileNotFoundError:
        logger.warning("yt-dlp가 설치되지 않았습니다. 설치를 시도합니다.")
        try:
            # yt-dlp 설치
            subprocess.run([sys.executable, '-m', 'pip', 'install', 'yt-dlp'], check=True)
            logger.info("yt-dlp 설치 완료")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"yt-dlp 설치 실패: {e}")
            return False
    except subprocess.CalledProcessError as e:
        logger.warning(f"yt-dlp 버전 확인 실패: {e}")
        # 업데이트 시도
        try:
            subprocess.run([sys.executable, '-m', 'pip', 'install', '--upgrade', 'yt-dlp'], check=True)
            logger.info("yt-dlp 업데이트 완료")
            return True
        except subprocess.CalledProcessError as update_e:
            logger.error(f"yt-dlp 업데이트 실패: {update_e}")
            return False

@shared_task
def download_video(url, user_id):
    """
    YouTube 동영상 다운로드 작업
    """
    job = None
    try:
        logger.info(f"다운로드 작업 시작: URL={url}, User ID={user_id}")
        logger.info(f"URL type: {type(url)}, User ID type: {type(user_id)}")
        
        # 작업 상태 업데이트
        user = User.objects.get(id=user_id)
        job = Job.objects.get(url=url, user=user, status='pending')
        logger.info(f"작업 찾음: Job ID={job.id}")
        
        # 1%로 먼저 시작
        job.status = 'processing'
        job.progress = 1
        job.save()
        logger.info(f"작업 상태 업데이트: status=processing, progress=1%")
        
        # yt-dlp 업데이트 확인
        if not ensure_yt_dlp():
            raise Exception("yt-dlp를 설치하거나 업데이트할 수 없습니다.")
        
        # 만약 제목이 없다면, 이 단계에서 가져옵니다
        if not job.title:
            try:
                # yt-dlp로 영상 정보 가져오기
                info_cmd = [
                    'yt-dlp',
                    '--dump-json',
                    '--no-playlist',
                    '--no-warnings',
                    url
                ]
                logger.info(f"영상 정보 가져오기 명령: {' '.join(info_cmd)}")
                info_result = subprocess.run(info_cmd, capture_output=True, text=True, check=True)
                video_info = json.loads(info_result.stdout)
                job.title = video_info.get('title', '')
                job.save()
                logger.info(f"영상 제목 가져옴: {job.title}")
            except subprocess.CalledProcessError as e:
                logger.warning(f"영상 제목 가져오기 실패 - stdout: {e.stdout}, stderr: {e.stderr}")
            except Exception as e:
                logger.warning(f"영상 제목 가져오기 실패: {str(e)}")
        
        # 다운로드할 디렉토리 생성
        media_root = settings.MEDIA_ROOT
        logger.info(f"MEDIA_ROOT: {media_root}, type: {type(media_root)}")
        user_dir = os.path.join(media_root, f'user_{user_id}')
        logger.info(f"User directory: {user_dir}, type: {type(user_dir)}")
        os.makedirs(user_dir, exist_ok=True)
        logger.info(f"사용자 디렉토리 생성: {user_dir}")
        
        # 임시 파일 경로
        temp_dir = tempfile.mkdtemp(dir=user_dir)
        logger.info(f"임시 디렉토리 생성: {temp_dir}")
        
        # 다운로드 명령 구성
        output_template = os.path.join(temp_dir, '%(id)s.%(ext)s')
        
        # YouTube Shorts인지 확인
        is_shorts = 'shorts/' in url
        logger.info(f"YouTube Shorts 여부: {is_shorts}")
        
        # 포맷 선택 최적화 - 테스트로 검증된 최고 해상도 조합
        if is_shorts:
            # Shorts의 경우 iOS 클라이언트를 사용하여 고해상도 접근
            extractor_args = 'youtube:player_client=ios'
            
            if job.quality == 'highest':
                # 1080p 우선, 없으면 720p, 그 다음 fallback
                format_selector = "270+234/232+234/231+234/230+234/18"
            elif job.quality == '720p':
                format_selector = "232+234/231+234/230+234/18"
            elif job.quality == '480p':
                format_selector = "231+234/230+234/18"
            elif job.quality == '360p':
                format_selector = "230+234/18"
            elif job.quality == 'audio':
                format_selector = "234/233"
            else:
                # 기본값: 가능한 한 높은 해상도
                format_selector = "270+234/232+234/231+234/230+234/18"
        else:
            # 일반 비디오 - 테스트로 검증된 포맷 ID 사용
            extractor_args = 'youtube:player_client=ios'
            
            if job.quality == 'highest':
                # Premium → AVC1 1080p → VP9 1080p → 720p 순으로 fallback
                # 오디오: 251(opus 고품질) → 140(m4a) → 234(m3u8) 순으로 fallback
                format_selector = "616+251/616+140/616+234/270+251/270+140/270+234/614+251/614+140/614+234/232+251/232+140/232+234/bestvideo[height>=1080]+bestaudio/bestvideo[height>=720]+bestaudio/bestvideo+bestaudio/best"
            elif job.quality == '720p':
                format_selector = "232+251/232+140/232+234/bestvideo[height>=720][height<=720]+bestaudio/bestvideo[height<=720]+bestaudio/best[height<=720]"
            elif job.quality == '480p':
                format_selector = "231+251/231+140/231+234/bestvideo[height>=480][height<=480]+bestaudio/bestvideo[height<=480]+bestaudio/best[height<=480]"
            elif job.quality == '360p':
                format_selector = "230+251/230+140/230+234/bestvideo[height>=360][height<=360]+bestaudio/bestvideo[height<=360]+bestaudio/best[height<=360]"
            elif job.quality == 'audio':
                format_selector = "251/140/234/233/bestaudio"
            else:
                # 기본값: 최고 품질
                format_selector = "616+251/616+140/616+234/270+251/270+140/270+234/614+251/614+140/614+234/232+251/232+140/232+234/bestvideo[height>=1080]+bestaudio/bestvideo+bestaudio/best"
        
        # 기본 yt-dlp 명령어
        cmd = [
            'yt-dlp',
            '-f', format_selector,
            '--no-playlist',
            '--no-warnings',
            '--no-check-certificate',
            '--user-agent', 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15',
            '--embed-chapters',  # 챕터 정보 포함
            '--write-info-json',  # 메타데이터 JSON 파일 저장
            '-o', output_template,
            url,
            '--extractor-args', extractor_args
        ]
        
        logger.info(f"다운로드 명령 실행: {' '.join(cmd)}")
        logger.info(f"선택된 포맷: {format_selector}")
        logger.info(f"사용 중인 extractor_args: {extractor_args}")
        
        # 명령 실행
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.info(f"yt-dlp 실행 성공 - stdout: {result.stdout}")
            if result.stderr:
                logger.warning(f"yt-dlp stderr: {result.stderr}")
        except subprocess.CalledProcessError as e:
            logger.error(f"yt-dlp 실행 실패: {e}")
            logger.error(f"stderr: {e.stderr}")
            logger.error(f"stdout: {e.stdout}")
            
            # 먼저 사용 가능한 포맷을 확인해보자
            logger.info("사용 가능한 포맷 확인 중...")
            format_check_cmd = [
                'yt-dlp',
                '-F',
                '--no-warnings',
                url,
                '--extractor-args', extractor_args
            ]
            try:
                format_result = subprocess.run(format_check_cmd, capture_output=True, text=True, check=True)
                logger.info(f"사용 가능한 포맷들:\n{format_result.stdout}")
            except subprocess.CalledProcessError as format_e:
                logger.error(f"포맷 확인 실패: {format_e.stderr}")
            
            # 1차 실패 시 fallback 포맷으로 재시도
            logger.info("더 간단한 포맷으로 재시도합니다...")
            fallback_cmd = [
                'yt-dlp',
                '-f', '270+251/270+140/232+251/232+140/18',  # 검증된 포맷 조합
                '--no-playlist',
                '--no-warnings', 
                '--no-check-certificate',
                '--user-agent', 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15',
                '-o', output_template,
                url,
                '--extractor-args', 'youtube:player_client=ios'
            ]
            logger.info(f"Fallback 명령 실행: {' '.join(fallback_cmd)}")
            
            try:
                result = subprocess.run(fallback_cmd, capture_output=True, text=True, check=True)
                logger.info(f"Fallback 다운로드 성공: {result.stdout}")
            except subprocess.CalledProcessError as fallback_e:
                logger.error(f"iOS Fallback 다운로드도 실패, Android로 재시도: {fallback_e}")
                
                # 마지막 시도: Android 클라이언트
                android_cmd = [
                    'yt-dlp',
                    '-f', '18',  # 기본 360p 포맷
                    '--no-playlist',
                    '--no-warnings', 
                    '--no-check-certificate',
                    '--user-agent', 'com.google.android.youtube/17.36.37 (Linux; U; Android 11)',
                    '-o', output_template,
                    url,
                    '--extractor-args', 'youtube:player_client=android'
                ]
                
                try:
                    result = subprocess.run(android_cmd, capture_output=True, text=True, check=True)
                    logger.info(f"Android fallback 다운로드 성공: {result.stdout}")
                except subprocess.CalledProcessError as android_e:
                    logger.error(f"모든 fallback 다운로드 실패: {android_e}")
                    raise Exception(f"다운로드 실패: {android_e.stderr}")
        
        # 10% 후 진행률 업데이트
        job.progress = 10
        job.save()
        logger.info(f"다운로드 준비 중: progress=10%")
        
        # 다운로드된 파일 찾기
        downloaded_files = [f for f in os.listdir(temp_dir) if os.path.isfile(os.path.join(temp_dir, f)) and not f.endswith('.info.json')]
        if not downloaded_files:
            # 디렉토리 내용 로깅
            all_files = os.listdir(temp_dir)
            logger.error(f"다운로드된 파일을 찾을 수 없음. 디렉토리 내용: {all_files}")
            raise Exception("다운로드된 파일을 찾을 수 없습니다.")
        
        # 첫 번째 다운로드된 파일 사용
        filename = downloaded_files[0]
        temp_file_path = os.path.join(temp_dir, filename)
        file_size = os.path.getsize(temp_file_path)
        
        logger.info(f"임시 파일 다운로드 완료: {temp_file_path}, 크기: {file_size} bytes")
        
        # 영구 저장소로 파일 이동
        permanent_dir = os.path.join(media_root, f'user_{user_id}', 'downloads')
        os.makedirs(permanent_dir, exist_ok=True)
        
        # 파일명에 타임스탬프 추가하여 중복 방지
        timestamp = int(time.time())
        name, ext = os.path.splitext(filename)
        permanent_filename = f"{name}_{timestamp}{ext}"
        permanent_file_path = os.path.join(permanent_dir, permanent_filename)
        
        # 파일 이동
        shutil.move(temp_file_path, permanent_file_path)
        logger.info(f"파일을 영구 저장소로 이동: {permanent_file_path}")
        
        # 임시 디렉토리 정리
        try:
            shutil.rmtree(temp_dir)
            logger.info(f"임시 디렉토리 정리: {temp_dir}")
        except Exception as cleanup_e:
            logger.warning(f"임시 디렉토리 정리 실패: {cleanup_e}")
        
        # 파일 타입 추정
        file_ext = os.path.splitext(permanent_filename)[1].lower()
        if file_ext in ['.mp4', '.mkv', '.webm', '.avi']:
            file_type = f'video/{file_ext[1:]}'
        elif file_ext in ['.mp3', '.m4a', '.wav', '.ogg']:
            file_type = f'audio/{file_ext[1:]}'
        else:
            file_type = 'application/octet-stream'
        
        # 파일 정보 저장 (영구 경로로)
        file = File.objects.create(
            job=job,
            filename=permanent_filename,
            file_path=permanent_file_path,
            file_size=file_size,
            file_type=file_type
        )
        logger.info(f"파일 정보 저장: file_id={file.id}, path={permanent_file_path}")
        
        # 작업 완료 상태 업데이트
        job.status = 'completed'
        job.progress = 100
        job.save()
        logger.info(f"작업 완료: status=completed, progress=100%")
        
        return {
            'status': 'success',
            'job_id': job.id,
            'file_id': file.id,
            'file_path': file.file_path,
            'filename': file.filename,
            'file_size': file_size
        }
        
    except Exception as e:
        # 오류 발생 시 작업 상태 업데이트
        error_message = str(e)
        logger.error(f"다운로드 작업 오류: {error_message}")
        
        if job:
            job.status = 'failed'
            job.error_message = error_message
            job.save()
            logger.error(f"작업 실패로 표시: job_id={job.id}")
        
        # 오류 로깅
        return {
            'status': 'error', 
            'error': error_message
        } 