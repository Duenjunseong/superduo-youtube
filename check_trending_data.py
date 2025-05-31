#!/usr/bin/env python
"""
수집된 YouTube 트렌딩 데이터를 확인하는 스크립트
"""
import os
import sys
import django

# Django 설정
if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()

from youtube_trending.models import TrendingVideo, TrendingStats
from datetime import date

def main():
    print('=== 트렌딩 비디오 통계 ===')
    total = TrendingVideo.objects.count()
    today_videos = TrendingVideo.objects.filter(trending_date=date.today()).count()
    shorts = TrendingVideo.objects.filter(is_shorts=True).count()
    
    print(f'총 수집된 비디오: {total}개')
    print(f'오늘 수집된 비디오: {today_videos}개')
    print(f'쇼츠 비디오: {shorts}개')
    
    print('\n=== 최근 수집된 비디오 (상위 5개) ===')
    recent_videos = TrendingVideo.objects.filter(trending_date=date.today()).order_by('trending_rank')[:5]
    for video in recent_videos:
        print(f'{video.trending_rank}. {video.title[:50]}... - {video.channel_title} ({video.duration})')
    
    print('\n=== 영상 길이별 분포 ===')
    duration_ranges = {
        '1분 이하 (쇼츠 후보)': 0,
        '1-5분': 0,
        '5-10분': 0,
        '10분 이상': 0,
        '알 수 없음': 0
    }
    
    for video in TrendingVideo.objects.filter(trending_date=date.today()):
        try:
            # Duration 파싱 (ISO 8601 형식)
            duration_str = video.duration
            if not duration_str or duration_str == 'Unknown':
                duration_ranges['알 수 없음'] += 1
                continue
                
            # PT1M30S -> 90초로 변환
            import re
            matches = re.findall(r'(\d+)([HMS])', duration_str)
            total_seconds = 0
            for value, unit in matches:
                if unit == 'H':
                    total_seconds += int(value) * 3600
                elif unit == 'M':
                    total_seconds += int(value) * 60
                elif unit == 'S':
                    total_seconds += int(value)
            
            if total_seconds <= 60:
                duration_ranges['1분 이하 (쇼츠 후보)'] += 1
            elif total_seconds <= 300:  # 5분
                duration_ranges['1-5분'] += 1
            elif total_seconds <= 600:  # 10분
                duration_ranges['5-10분'] += 1
            else:
                duration_ranges['10분 이상'] += 1
                
        except Exception as e:
            duration_ranges['알 수 없음'] += 1
    
    for range_name, count in duration_ranges.items():
        print(f'{range_name}: {count}개')
    
    print('\n=== 수집 통계 ===')
    stats = TrendingStats.objects.filter(collection_date=date.today()).first()
    if stats:
        print(f'수집 날짜: {stats.collection_date}')
        print(f'수집 성공: {stats.collection_success}')
        print(f'총 수집: {stats.total_videos_collected}개')
        print(f'쇼츠: {stats.shorts_count}개')
        print(f'일반 영상: {stats.regular_videos_count}개')
    else:
        print('오늘의 수집 통계가 없습니다.')
    
    # 일부 영상의 상세 정보
    print('\n=== 상세 정보 (첫 3개 영상) ===')
    for video in recent_videos[:3]:
        print(f'\n제목: {video.title}')
        print(f'채널: {video.channel_title}')
        print(f'조회수: {video.formatted_view_count}')
        print(f'길이: {video.duration} ({video.formatted_duration})')
        print(f'쇼츠 여부: {video.is_shorts}')
        print(f'카테고리: {video.get_category_display()}')
        print(f'트렌딩 순위: {video.trending_rank}')

if __name__ == '__main__':
    main() 