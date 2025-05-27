import re
import subprocess
from pathlib import Path
from typing import Tuple, List
from django.conf import settings
import logging
import yt_dlp

logger = logging.getLogger(__name__)

def parse_time_range(time_range_str: str) -> Tuple[str, str]:
    """시간 범위 문자열 (예: "00:01:00-00:02:30")을 시작과 끝 시간으로 분리"""
    parts = re.split(r'~|-', time_range_str.strip())
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    raise ValueError(f"잘못된 시간 범위 형식입니다: {time_range_str}")

def time_to_seconds(time_str: str) -> float:
    """시간 문자열(HH:MM:SS 또는 MM:SS 또는 SS)을 초 단위로 변환.
       각 시간 구성요소의 상한선을 검사합니다."""
    parts_str = time_str.split(':')
    
    if not (1 <= len(parts_str) <= 3):
        raise ValueError(f"시간 형식은 1~3개의 부분으로 구성되어야 합니다: {time_str}")

    try:
        parts_float = [float(p) for p in parts_str]
    except ValueError:
        raise ValueError(f"시간 구성요소는 숫자여야 합니다: {time_str}")

    h, m, s = 0.0, 0.0, 0.0

    if len(parts_float) == 1:
        s = parts_float[0]
        if not (0 <= s < 60000): # 예: 최대 약 16시간 분량의 초, 필요시 조정
            raise ValueError(f"초(s) 값은 0과 60000 사이여야 합니다: {s}")
        return s
    elif len(parts_float) == 2:
        m, s = parts_float[0], parts_float[1]
        if not (0 <= m < 60):
            raise ValueError(f"분(m) 값은 0과 59 사이여야 합니다: {m}")
        if not (0 <= s < 60):
            raise ValueError(f"초(s) 값은 0과 59 사이여야 합니다: {s}")
        return m * 60 + s
    elif len(parts_float) == 3:
        h, m, s = parts_float[0], parts_float[1], parts_float[2]
        # 예: 시간은 최대 99999 시간으로 제한 (약 11년). 이는 3.6 * 10^8 초로, BigIntegerField에 안전.
        if not (0 <= h < 100000): 
            raise ValueError(f"시간(h) 값은 0과 99999 사이여야 합니다: {h}")
        if not (0 <= m < 60):
            raise ValueError(f"분(m) 값은 0과 59 사이여야 합니다: {m}")
        if not (0 <= s < 60):
            raise ValueError(f"초(s) 값은 0과 59 사이여야 합니다: {s}")
        return h * 3600 + m * 60 + s

def sanitize_filename(filename: str) -> str:
    """파일 이름에서 안전하지 않은 문자를 제거하고 공백을 밑줄로 변경"""
    sanitized = re.sub(r'[\\/*?:"<>|]', "", filename)
    sanitized = re.sub(r'\s+', '_', sanitized) # 공백을 밑줄로
    sanitized = sanitized.strip(" .")
    return sanitized

def split_video_segment(
    original_video_path: Path,
    output_directory: Path,
    output_filename_stem: str, # 확장자 제외 파일명 (예: "my_video_segment_1")
    start_seconds: float,  # 변경: start_time_str -> start_seconds (float 또는 int)
    end_seconds: float,    # 변경: end_time_str -> end_seconds (float 또는 int)
    video_suffix: str = ".mp4" # 원본 영상 확장자
) -> Tuple[bool, Path | None]:
    """FFmpeg를 사용하여 단일 비디오 세그먼트를 자릅니다."""
    try:
        # start_seconds = time_to_seconds(start_time_str) # 이미 초 단위로 받으므로 주석 처리 또는 삭제
        # end_seconds = time_to_seconds(end_time_str)   # 이미 초 단위로 받으므로 주석 처리 또는 삭제
        duration_seconds = end_seconds - start_seconds

        if duration_seconds <= 0:
            # logger.error(f"종료 시간({end_time_str})이 시작 시간({start_time_str})보다 빠르거나 같을 수 없습니다.")
            logger.error(f"종료 시간({end_seconds}s)이 시작 시간({start_seconds}s)보다 빠르거나 같을 수 없습니다.")
            return False, None

        # 출력 파일명에 원본 확장자 사용
        output_filename = f"{sanitize_filename(output_filename_stem)}{video_suffix}"
        output_path = output_directory / output_filename
        output_directory.mkdir(parents=True, exist_ok=True)

        cmd = [
            'ffmpeg', '-y',
            '-ss', str(start_seconds),         # 초 단위 직접 사용
            '-i', str(original_video_path),
            '-t', str(duration_seconds),      # 지속 시간도 초 단위로 직접 사용
            '-c', 'copy', # 스트림 복사
            '-avoid_negative_ts', '1',
            '-map_metadata', '0',
            '-movflags', '+faststart',
            str(output_path)
        ]

        logger.info(f"FFmpeg 명령어 실행 중: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=False) # check=False로 변경하여 stderr 직접 처리

        if result.returncode != 0:
            logger.error(f"FFmpeg 오류 발생 (명령어: {' '.join(cmd)}):\n{result.stderr}")
            return False, None
        else:
            logger.info(f"파일 생성 완료: {output_path}")
            if result.stderr: # 오류가 아니더라도 FFmpeg가 stderr에 정보를 출력할 수 있음
                logger.info(f"FFmpeg 출력 (stderr):\n{result.stderr}")
            return True, output_path

    except ValueError as ve:
        logger.error(f"시간 파싱 오류: {ve}")
        return False, None
    except FileNotFoundError:
        logger.error(f"FFmpeg를 찾을 수 없습니다. PATH 환경변수를 확인하세요.")
        return False, None
    except Exception as e:
        logger.error(f"세그먼트 분할 중 예기치 않은 오류 발생: {e}", exc_info=True)
        return False, None

# split_project의 stream_copy_ffmpeg와 유사하게 여러 시간 범위를 처리하는 래퍼 함수 (선택 사항)
# def process_multiple_segments(video_path: Path, time_ranges_with_ids: List[Tuple[str, str, str]], base_output_dir: Path, ...)
# 이 함수는 Celery 태스크 내에서 호출될 수 있습니다. 

def get_youtube_video_title(youtube_url: str) -> str:
    """
    yt-dlp를 사용하여 YouTube 비디오의 제목을 가져옵니다.
    실패 시 '제목 미탐지'를 반환합니다.
    """
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'skip_download': True,  # 다운로드하지 않고 정보만 가져오기
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            title = info.get('title', '제목 미탐지')
            
            # 제목이 너무 길면 자르기 (DB 필드 길이 제한 고려)
            if len(title) > 450:  # 여유를 두고 450자로 제한
                title = title[:447] + '...'
                
            logger.info(f"YouTube 제목 추출 성공: {title}")
            return title
            
    except Exception as e:
        logger.error(f"YouTube 제목 추출 실패 ({youtube_url}): {e}")
        return '제목 미탐지' 