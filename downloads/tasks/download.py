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
        user_dir = os.path.join(media_root, f'user_{user_id}')
        os.makedirs(user_dir, exist_ok=True)
        logger.info(f"사용자 디렉토리 생성: {user_dir}")
        
        # 임시 파일 경로
        temp_dir = tempfile.mkdtemp(dir=user_dir)
        logger.info(f"임시 디렉토리 생성: {temp_dir}")
        
        # 품질 설정에 따른 yt-dlp 포맷 선택
        if job.quality == 'highest':
            format_spec = 'best'  # 단순화
        elif job.quality == '720p':
            format_spec = 'best[height<=720]'
        elif job.quality == '480p':
            format_spec = 'best[height<=480]'
        elif job.quality == '360p':
            format_spec = 'best[height<=360]'
        elif job.quality == 'audio':
            format_spec = 'bestaudio'
        else:
            format_spec = 'best'
        
        # 파일명 설정 (더 안전한 템플릿)
        # YouTube ID를 사용하여 안전한 파일명 생성
        output_template = os.path.join(temp_dir, '%(id)s.%(ext)s')
        
        # 진행 상황 업데이트를 위한 함수
        job.progress = 10
        job.save()
        logger.info(f"다운로드 준비 중: progress=10%")
        
        # YouTube Shorts인지 확인
        is_shorts = 'shorts/' in url.lower()
        logger.info(f"YouTube Shorts 여부: {is_shorts}")
        
        # yt-dlp를 사용하여 실제 다운로드
        cmd = [
            'yt-dlp',
            '-f', format_spec,
            '--no-playlist',
            '--no-warnings',
            '--no-check-certificate',  # SSL 인증서 문제 방지
            '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',  # User-Agent 설정
            '-o', output_template,
            url
        ]
        
        # Shorts의 경우 특별한 옵션 추가
        if is_shorts:
            cmd.extend(['--extractor-args', 'youtube:player_client=android'])
        
        logger.info(f"다운로드 명령 실행: {' '.join(cmd)}")
        
        # subprocess 실행 시 더 자세한 에러 정보 수집
        try:
            process = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=600)  # 10분 타임아웃
            logger.info(f"yt-dlp 실행 성공 - stdout: {process.stdout}")
        except subprocess.CalledProcessError as e:
            error_msg = f"yt-dlp 실행 실패 (exit code {e.returncode})\n"
            error_msg += f"명령어: {' '.join(cmd)}\n"
            error_msg += f"stdout: {e.stdout}\n"
            error_msg += f"stderr: {e.stderr}\n"
            logger.error(error_msg)
            
            # 일반적인 에러 메시지 변환
            stderr_lower = e.stderr.lower() if e.stderr else ""
            if "video unavailable" in stderr_lower or "private video" in stderr_lower:
                raise Exception("비디오를 사용할 수 없습니다. 개인 비디오이거나 삭제된 비디오일 수 있습니다.")
            elif "requested format is not available" in stderr_lower:
                raise Exception("요청한 품질의 비디오를 사용할 수 없습니다. 다른 품질을 선택해주세요.")
            elif "this video is not available" in stderr_lower:
                raise Exception("이 비디오는 사용할 수 없습니다.")
            elif "sign in to confirm your age" in stderr_lower:
                raise Exception("연령 제한이 있는 비디오입니다.")
            elif "this video has been removed" in stderr_lower:
                raise Exception("이 비디오는 삭제되었습니다.")
            elif "no video formats found" in stderr_lower:
                # 폴백: 더 단순한 포맷으로 재시도
                logger.info("포맷을 찾을 수 없음. 기본 포맷으로 재시도...")
                fallback_cmd = [
                    'yt-dlp',
                    '--no-playlist',
                    '--no-warnings',
                    '-o', output_template,
                    url
                ]
                try:
                    fallback_process = subprocess.run(fallback_cmd, check=True, capture_output=True, text=True, timeout=600)
                    logger.info(f"폴백 다운로드 성공: {fallback_process.stdout}")
                except subprocess.CalledProcessError as fallback_e:
                    raise Exception(f"다운로드 실패: {fallback_e.stderr}")
            else:
                raise Exception(f"다운로드 실패: {e.stderr or '알 수 없는 오류'}")
        except subprocess.TimeoutExpired:
            raise Exception("다운로드 시간이 초과되었습니다. 나중에 다시 시도해주세요.")
        
        job.progress = 70
        job.save()
        logger.info(f"다운로드 진행 중: progress=70%")
        
        # 다운로드된 파일 찾기
        downloaded_files = [f for f in os.listdir(temp_dir) if os.path.isfile(os.path.join(temp_dir, f)) and not f.endswith('.info.json')]
        if not downloaded_files:
            # 디렉토리 내용 로깅
            all_files = os.listdir(temp_dir)
            logger.error(f"다운로드된 파일을 찾을 수 없음. 디렉토리 내용: {all_files}")
            raise Exception("다운로드된 파일을 찾을 수 없습니다.")
        
        # 첫 번째 다운로드된 파일 사용
        filename = downloaded_files[0]
        file_path = os.path.join(temp_dir, filename)
        file_size = os.path.getsize(file_path)
        
        logger.info(f"파일 다운로드 완료: {file_path}, 크기: {file_size} bytes")
        
        # 파일 타입 추정
        file_ext = os.path.splitext(filename)[1].lower()
        if file_ext in ['.mp4', '.mkv', '.webm', '.avi']:
            file_type = f'video/{file_ext[1:]}'
        elif file_ext in ['.mp3', '.m4a', '.wav', '.ogg']:
            file_type = f'audio/{file_ext[1:]}'
        else:
            file_type = 'application/octet-stream'
        
        # 파일 정보 저장
        file = File.objects.create(
            job=job,
            filename=filename,
            file_path=file_path,
            file_size=file_size,
            file_type=file_type
        )
        logger.info(f"파일 정보 저장: file_id={file.id}")
        
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