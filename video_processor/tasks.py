from celery import shared_task
import yt_dlp
from pathlib import Path
from django.conf import settings
import logging
import os

from .models import ProcessingJob, VideoSegment
from .utils import split_video_segment, sanitize_filename, parse_time_range

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=60) # bind=True로 task 객체 접근, 재시도 설정
def download_and_process_video_task(self, job_id):
    try:
        job = ProcessingJob.objects.get(job_id=job_id)
        job.status = 'DOWNLOADING'
        job.save()

        # 1. 영상 다운로드 (yt-dlp 라이브러리 사용)
        original_videos_dir = Path(settings.MEDIA_ROOT) / 'original_videos' / str(job.job_id)
        original_videos_dir.mkdir(parents=True, exist_ok=True)

        # yt-dlp 옵션 설정 (파일명, 경로 등)
        # 원본 영상의 확장자를 알기 위해 먼저 정보를 가져오거나, 일반적인 mp4로 저장 시도
        temp_filename = 'source' # 확장자 없이 임시 파일명
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best', # mp4 선호
            'outtmpl': str(original_videos_dir / f'{temp_filename}.%(ext)s'),
            'noplaylist': True,
            'quiet': True,
            'merge_output_format': 'mp4',
        }

        downloaded_file_path = None
        video_suffix = '.mp4' # 기본값

        logger.info(f"[{job_id}] 유튜브 영상 다운로드 시작: {job.youtube_url}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(job.youtube_url, download=True)
            # 실제 다운로드된 파일명과 확장자 가져오기
            # ydl.prepare_filename(info_dict)는 전체 경로를 포함한 파일명을 반환
            # 실제 저장된 파일명을 찾아야 함
            temp_full_path_pattern = original_videos_dir / f"{temp_filename}.*"
            # glob을 사용하여 실제 생성된 파일을 찾습니다.
            downloaded_files = list(original_videos_dir.glob(f'{temp_filename}.*'))
            if not downloaded_files:
                raise Exception("yt-dlp가 파일을 생성했지만, 예상 경로에서 찾을 수 없습니다.")
            
            downloaded_file_path = downloaded_files[0] # 첫 번째 매칭 파일
            video_suffix = downloaded_file_path.suffix # 실제 확장자 사용
            
            # 최종 파일명을 job_id 기반으로 변경 (선택적, 이미 디렉토리로 구분됨)
            final_original_video_path = original_videos_dir / f"original{video_suffix}"
            downloaded_file_path.rename(final_original_video_path)
            downloaded_file_path = final_original_video_path
            
        job.downloaded_video_path = str(downloaded_file_path.relative_to(settings.MEDIA_ROOT))
        job.status = 'PROCESSING'
        job.save()
        logger.info(f"[{job_id}] 다운로드 완료: {job.downloaded_video_path}")

        # 2. 각 세그먼트 처리
        segments = job.segments.filter(status='PENDING') # 아직 처리 안된 세그먼트만
        if not segments.exists():
            logger.warning(f"[{job_id}] 처리할 PENDING 상태의 세그먼트가 없습니다.")
            job.status = 'COMPLETED' # 다운로드만 하고 자를 구간이 없을 수도 있음
            job.save()
            return f"Job {job_id}: 다운로드 완료, 처리할 세그먼트 없음"

        all_segments_processed_successfully = True
        for segment in segments:
            segment.status = 'PROCESSING'
            segment.save()
            logger.info(f"[{job_id}] 세그먼트 처리 시작: {segment.segment_id}")
            
            output_segments_dir = Path(settings.MEDIA_ROOT) / 'processed_segments' / str(job.job_id)
            output_segments_dir.mkdir(parents=True, exist_ok=True)
            
            # output_filename_prefix가 있으면 사용, 없으면 segment_id 사용
            filename_stem = segment.output_filename_prefix if segment.output_filename_prefix else str(segment.segment_id)
            
            # 전체 파일 다운로드인지 확인 (end_time이 -1인 경우)
            if segment.end_time == -1:
                # 전체 파일 복사
                output_filename = f"{sanitize_filename(filename_stem)}{video_suffix}"
                output_path = output_segments_dir / output_filename
                
                try:
                    # 원본 파일을 출력 디렉토리로 복사
                    import shutil
                    shutil.copy2(downloaded_file_path, output_path)
                    
                    segment.processed_file_path = str(output_path.relative_to(settings.MEDIA_ROOT))
                    segment.status = 'COMPLETED'
                    logger.info(f"[{job_id}] 전체 파일 복사 완료: {segment.segment_id} -> {segment.processed_file_path}")
                except Exception as e:
                    segment.status = 'FAILED'
                    all_segments_processed_successfully = False
                    logger.error(f"[{job_id}] 전체 파일 복사 실패: {segment.segment_id}, 오류: {e}")
            else:
                # 기존 세그먼트 분할 로직
                success, processed_path = split_video_segment(
                    original_video_path=downloaded_file_path, 
                    output_directory=output_segments_dir,
                    output_filename_stem=filename_stem,
                    start_seconds=float(segment.start_time),
                    end_seconds=float(segment.end_time),
                    video_suffix=video_suffix # 원본 영상의 실제 확장자 전달
                )
                
                if success and processed_path:
                    segment.processed_file_path = str(processed_path.relative_to(settings.MEDIA_ROOT))
                    segment.status = 'COMPLETED'
                    logger.info(f"[{job_id}] 세그먼트 처리 완료: {segment.segment_id} -> {segment.processed_file_path}")
                else:
                    segment.status = 'FAILED'
                    all_segments_processed_successfully = False
                    logger.error(f"[{job_id}] 세그먼트 처리 실패: {segment.segment_id}")
            
            segment.save()

        if all_segments_processed_successfully:
            job.status = 'COMPLETED'
            logger.info(f"[{job_id}] 모든 세그먼트 처리 완료.")
        else:
            job.status = 'FAILED' # 하나라도 실패하면 작업 실패 처리
            logger.warning(f"[{job_id}] 일부 세그먼트 처리에 실패했습니다.")
        job.save()

        return f"Job {job_id} 처리 완료. 상태: {job.status}"

    except ProcessingJob.DoesNotExist:
        logger.error(f"[TaskError] Job ID {job_id}를 찾을 수 없습니다.")
        # 재시도 불필요
        return f"Job ID {job_id} 없음"
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"[{job_id if 'job_id' in locals() else 'UnknownJob'}] yt-dlp 다운로드 오류: {e}")
        if 'job' in locals():
            job.status = 'FAILED'
            job.save()
        # self.retry(exc=e) # 설정된 횟수만큼 재시도
        raise # Celery가 재시도하도록 예외 다시 발생
    except Exception as e:
        logger.error(f"[{job_id if 'job_id' in locals() else 'UnknownJob'}] 예상치 못한 오류 발생: {e}", exc_info=True)
        if 'job' in locals():
            job.status = 'FAILED'
            job.save()
        # self.retry(exc=e)
        raise

# 개별 세그먼트 처리 태스크 (선택 사항, 위 태스크에 통합됨)
# @shared_task
# def process_single_segment_task(segment_id):
# ... (download_and_process_video_task 내부의 세그먼트 처리 로직과 유사) 