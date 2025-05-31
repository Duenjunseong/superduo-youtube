#!/usr/bin/env python
"""
테스트용 쇼츠 데이터를 생성하는 스크립트
"""
import os
import sys
import django

# Django 설정
if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()

from youtube_trending.models import TrendingVideo
from datetime import date

def main():
    # 기존 영상 중 상위 5개를 테스트용 쇼츠로 변경
    videos = TrendingVideo.objects.filter(trending_date=date.today()).order_by('trending_rank')[:5]
    
    print(f'총 {videos.count()}개 영상을 테스트용 쇼츠로 설정합니다...')
    
    for video in videos:
        video.is_shorts = True
        video.save()
        print(f'✓ 쇼츠로 설정: #{video.trending_rank} {video.title[:40]}...')
    
    # 통계 확인
    total_shorts = TrendingVideo.objects.filter(is_shorts=True).count()
    print(f'\n현재 총 쇼츠 개수: {total_shorts}개')
    
    # 쇼츠 목록 출력
    print('\n=== 현재 쇼츠 목록 ===')
    shorts = TrendingVideo.objects.filter(is_shorts=True, trending_date=date.today()).order_by('trending_rank')
    for short in shorts:
        print(f'#{short.trending_rank} {short.title} - {short.channel_title}')
        print(f'  조회수: {short.formatted_view_count}, 길이: {short.formatted_duration}')

if __name__ == '__main__':
    main() 