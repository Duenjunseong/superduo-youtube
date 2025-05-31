#!/usr/bin/env python3
"""
수집된 쇼츠 데이터의 정확도 검증 스크립트
"""

import os
import sys
import django
from datetime import datetime, date

# Django 설정
sys.path.append('/Users/dev-jun/PROJECT/슈퍼듀오자동화툴/django_youtube')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from youtube_trending.services import YouTubeTrendingScraper, YouTubeMetadataExtractor
from youtube_trending.models import TrendingVideo
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def validate_collected_data():
    """수집된 데이터의 정확도를 검증합니다."""
    
    print("=== 수집된 쇼츠 데이터 정확도 검증 ===\n")
    
    # 1. 데이터베이스에서 최신 쇼츠 데이터 조회
    latest_shorts = TrendingVideo.objects.filter(
        trending_date=date.today(),
        is_shorts=True
    ).order_by('trending_rank')
    
    print(f"📊 오늘 수집된 쇼츠 데이터: {latest_shorts.count()}개")
    
    if not latest_shorts.exists():
        print("❌ 오늘 수집된 쇼츠 데이터가 없습니다.")
        return
    
    # 2. YouTube ID 유효성 검증
    print("\n🔍 YouTube ID 유효성 검증:")
    valid_ids = 0
    invalid_ids = []
    
    for shorts in latest_shorts:
        if shorts.youtube_id and len(shorts.youtube_id) >= 8:
            valid_ids += 1
            print(f"  ✅ {shorts.trending_rank}. {shorts.youtube_id}")
        else:
            invalid_ids.append(shorts.youtube_id)
            print(f"  ❌ {shorts.trending_rank}. {shorts.youtube_id} (유효하지 않음)")
    
    print(f"\n📈 ID 유효성: {valid_ids}/{latest_shorts.count()} ({valid_ids/latest_shorts.count()*100:.1f}%)")
    
    # 3. 제목 정보 품질 분석
    print("\n📝 제목 정보 품질 분석:")
    meaningful_titles = 0
    
    for shorts in latest_shorts:
        title = shorts.title or ""
        if len(title) > 10 and not title.startswith('쇼츠 '):
            meaningful_titles += 1
            print(f"  ✅ {shorts.trending_rank}. {title[:50]}...")
        else:
            print(f"  ⚠️  {shorts.trending_rank}. {title} (의미있는 제목 없음)")
    
    print(f"\n📈 제목 품질: {meaningful_titles}/{latest_shorts.count()} ({meaningful_titles/latest_shorts.count()*100:.1f}%)")
    
    # 4. 조회수 정보 분석
    print("\n👁️  조회수 정보 분석:")
    valid_view_counts = 0
    
    for shorts in latest_shorts:
        if shorts.view_count and shorts.view_count > 0:
            valid_view_counts += 1
            # 조회수를 한국어 형식으로 변환
            if shorts.view_count >= 10000:
                view_display = f"{shorts.view_count//10000}만회"
            elif shorts.view_count >= 1000:
                view_display = f"{shorts.view_count//1000}천회"
            else:
                view_display = f"{shorts.view_count}회"
            print(f"  ✅ {shorts.trending_rank}. {view_display}")
        else:
            print(f"  ❌ {shorts.trending_rank}. 조회수 정보 없음")
    
    print(f"\n📈 조회수 품질: {valid_view_counts}/{latest_shorts.count()} ({valid_view_counts/latest_shorts.count()*100:.1f}%)")
    
    # 5. 실제 YouTube에서 접근 가능한지 검증 (샘플)
    print("\n🌐 실제 접근성 검증 (상위 5개):")
    metadata_extractor = YouTubeMetadataExtractor()
    
    accessible_count = 0
    test_count = min(5, latest_shorts.count())
    
    for i, shorts in enumerate(latest_shorts[:test_count], 1):
        try:
            # yt-dlp로 실제 메타데이터 추출 시도
            metadata = metadata_extractor.extract_video_metadata(shorts.youtube_id)
            if metadata:
                accessible_count += 1
                actual_title = metadata.get('title', '')[:50]
                print(f"  ✅ {i}. {shorts.youtube_id} - {actual_title}...")
            else:
                print(f"  ❌ {i}. {shorts.youtube_id} - 접근 불가")
        except Exception as e:
            print(f"  ⚠️  {i}. {shorts.youtube_id} - 검증 실패: {str(e)[:30]}...")
    
    print(f"\n📈 실제 접근성 (샘플): {accessible_count}/{test_count} ({accessible_count/test_count*100:.1f}%)")
    
    # 6. 종합 품질 점수
    print("\n🏆 종합 품질 분석:")
    total_score = 0
    
    # ID 유효성 (30점)
    id_score = (valid_ids / latest_shorts.count()) * 30
    total_score += id_score
    print(f"  ID 유효성: {id_score:.1f}/30점")
    
    # 제목 품질 (25점)
    title_score = (meaningful_titles / latest_shorts.count()) * 25
    total_score += title_score
    print(f"  제목 품질: {title_score:.1f}/25점")
    
    # 조회수 정보 (25점)
    view_score = (valid_view_counts / latest_shorts.count()) * 25
    total_score += view_score
    print(f"  조회수 정보: {view_score:.1f}/25점")
    
    # 접근성 (20점) - 샘플 기반 추정
    access_score = (accessible_count / test_count) * 20 if test_count > 0 else 0
    total_score += access_score
    print(f"  실제 접근성: {access_score:.1f}/20점")
    
    print(f"\n🎯 총점: {total_score:.1f}/100점")
    
    if total_score >= 80:
        grade = "A급 (우수)"
    elif total_score >= 60:
        grade = "B급 (양호)"
    elif total_score >= 40:
        grade = "C급 (보통)"
    else:
        grade = "D급 (미흡)"
    
    print(f"🏅 데이터 품질 등급: {grade}")
    
    # 7. 세부 데이터 출력
    print(f"\n📋 수집된 쇼츠 상세 정보:")
    for shorts in latest_shorts:
        print(f"  {shorts.trending_rank}. {shorts.youtube_id}")
        print(f"     제목: {shorts.title}")
        print(f"     조회수: {shorts.view_count:,}회" if shorts.view_count else "     조회수: 정보없음")
        print(f"     채널: {shorts.channel_title}" if shorts.channel_title else "     채널: 정보없음")
        print()
    
    # 8. 결론
    print("🎯 결론:")
    if latest_shorts.count() >= 10 and total_score >= 60:
        print("✅ 수집된 데이터가 충분하고 품질이 양호합니다!")
        print("   이 데이터로 트렌딩 쇼츠 분석이 가능합니다.")
    elif latest_shorts.count() >= 5:
        print("⚠️  데이터 수는 적당하지만 품질 개선이 필요할 수 있습니다.")
    else:
        print("❌ 데이터 수가 부족합니다. 수집 전략을 개선해야 합니다.")

if __name__ == "__main__":
    validate_collected_data() 