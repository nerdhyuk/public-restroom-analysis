import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import folium
from folium.plugins import MarkerCluster
import re
import warnings
warnings.simplefilter("ignore")


# 파일 경로
path = 'C:/Users/anton/restroom_data/'

# 데이터 불러오기
seoul_df = pd.read_excel(path + '서울_공중화장실정보.xlsx')
busan_df = pd.read_excel(path + '부산_공중화장실정보.xlsx')
jeju_df = pd.read_excel(path + '제주도_공중화장실정보.xlsx')

# 데이터 구조 확인
# print(seoul_df.columns)
# print(seoul_df.head())

# 컬럼명 영문화
rename_dict = {
    # 접근성 관련
    '남성용-장애인용대변기수': 'male_disabled_toilet_count',
    '여성용-장애인용대변기수': 'female_disabled_toilet_count',
    '기저귀교환대유무': 'has_diaper_table',
    '기저귀교환대장소': 'diaper_table_location',
    'WGS84위도': 'latitude',
    'WGS84경도': 'longitude',
    '소재지도로명주소': 'address_road',
    # 안전성 관련
    '비상벨설치여부': 'emergency_bell_installed',
    '비상벨설치장소': 'emergency_bell_location',
    '화장실입구CCTV설치유무': 'has_cctv',
    '안전관리시설설치대상여부': 'safety_facility_required'
}

# 지역 정보 추가 및 컬럼명 변경
for df, region in zip([seoul_df, busan_df, jeju_df], ['서울', '부산', '제주도']):
    df.rename(columns=rename_dict, inplace=True)
    df['region'] = region

# 데이터 통합
df = pd.concat([seoul_df, busan_df, jeju_df], ignore_index=True)

# 접근성 점수 계산
df['accessibility_score'] = (
    df['male_disabled_toilet_count'].fillna(0).astype(int) +
    df['female_disabled_toilet_count'].fillna(0).astype(int) +
    df['has_diaper_table'].apply(lambda x: 1 if str(x).strip() == 'Y' else 0)
)

# 안전성 점수 계산
df['safety_score'] = (
    df['emergency_bell_installed'].apply(lambda x: 1 if str(x).strip() == 'Y' else 0) +
    df['has_cctv'].apply(lambda x: 1 if str(x).strip() == 'Y' else 0) +
    df['safety_facility_required'].apply(lambda x: 1 if str(x).strip() == 'Y' else 0)
)

# 지역별 평균 점수 비교
region_summary = df.groupby('region')[['accessibility_score', 'safety_score']].mean().round(2)
# print(region_summary)

'''
        accessibility_score  safety_score
region                                   
부산                     1.24          0.77
서울                     1.33          1.36
제주도                    1.33          1.78

- 제주도는 비상벨, CCTV, 안전관리시설 설치 비율이 높아 안전성 지표가 가장 우수함.
- 부산은 접근성 점수가 낮은 편이고, 특히 안전성 점수가 가장 낮아 개선이 시급함.
- 서울은 두 지표 모두 고르게 높아 균형 잡힌 인프라를 갖추고 있음.
'''


# '구' 추출 함수
def extract_gu(address):
    try:
        match = re.search(r'([가-힣]+구)\b', address)
        if match:
            gu = match.group(1)
            if gu in ['출입구', '입구', '출구']:
                return None
            return gu
    except:
        return None

# 'district' 컬럼 생성
df['district'] = None
df.loc[df['region'].isin(['서울', '부산']), 'district'] = df.loc[df['region'].isin(['서울', '부산']), 'address_road'].apply(extract_gu)
df.loc[df['region'] == '제주도', 'district'] = df.loc[df['region'] == '제주도', 'address_road']  # 제주도는 주소 그대로

# 지역별 평균 접근성 점수 계산
mainland_summary = df[df['region'].isin(['서울', '부산'])].groupby('region')[['accessibility_score']].mean().round(2).reset_index()
jeju_score = df[df['region'] == '제주도']['accessibility_score'].mean().round(2)
jeju_summary = pd.DataFrame({'region': ['제주도'], 'accessibility_score': [jeju_score]})
region_summary = pd.concat([mainland_summary, jeju_summary], ignore_index=True)

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

# 색상 지정
region_colors = {
    '서울': '#87CEEB',
    '부산': '#00CED1',
    '제주도': '#4682B4'
}

## 시각화
# plt.figure(figsize=(8, 5))
# sns.barplot(
#     x='region',
#     y='accessibility_score',
#     hue='region',
#     data=region_summary,
#     palette=region_colors,
#     legend=False
# )

# plt.title('지역별 접근성 점수 비교', fontsize=16, pad=20)
# plt.xlabel('지역', fontsize=12)
# plt.ylabel('접근성 점수', fontsize=12)
# plt.xticks(fontsize=11)
# plt.yticks(fontsize=11)
# plt.tight_layout()
# plt.show()


# 접근성 점수 0인 지점 확인
district_summary = (
    df.groupby(['region', 'district'], dropna=False)[['accessibility_score', 'safety_score']]
    .mean()
    .round(2)
    .reset_index()
)

# address_road - NaN값 삭제
df = df[df['address_road'].notna()]

# 접근성 점수가 0인 공중화장실 지점들 중 상위 20개
zero_access_all = df[df['accessibility_score'] == 0]
# print(zero_access_all[['region', 'address_road', 'district', 'accessibility_score', 'safety_score']].head(20))


## folium 작업
# 1. 좌표 기반 지역 분류 함수 (위도 + 경도 기준으로 정밀하게)
def classify_region_by_latlon(lat, lon):
    if 33 < lat < 34.5 and 126 < lon < 127.2:
        return '제주도'
    elif 34.8 < lat < 35.4 and 128.8 < lon < 129.3:
        return '부산'
    elif 37.4 < lat < 37.7 and 126.8 < lon < 127.2:
        return '서울'
    else:
        return '기타'

# 2. 지도용 데이터 정리
df_map = df.dropna(subset=['latitude', 'longitude']).copy()

# 좌표 기반 지역명 생성
df_map['region_by_coord'] = df_map.apply(lambda row: classify_region_by_latlon(row['latitude'], row['longitude']), axis=1)

# 주소 기반 지역은 유지하고, 좌표 기반 지역과 비교
df_clean = df_map[df_map['region'] == df_map['region_by_coord']].copy()

# 오류 좌표 제거: 주소 기반 지역과 좌표 기반 지역이 다른 지점 제외
df_map = df_map[df_map['region'] == df_map['region_by_coord']]

# 3. 지도 생성
map_center = [37.5665, 126.9780]  # 서울 시청 기준
restroom_map = folium.Map(location=map_center, zoom_start=11)
marker_cluster = MarkerCluster().add_to(restroom_map)

# 4. 색상 함수 (접근성 점수 기준)
def get_color(score):
    if score >= 3:
        return 'green'
    elif score >= 2:
        return 'orange'
    else:
        return 'red'

# 5. 마커 생성
for _, row in df_map.iterrows():
    lat = row['latitude']
    lon = row['longitude']
    acc = row['accessibility_score']
    safe = row['safety_score']
    name = row.get('toilet_name') or row.get('address_road', '주소 없음')
    region = row.get('region_by_coord', '지역 없음')
    district = row.get('district', '구 정보 없음')

    popup_text = f"""
    <b>{name}</b><br>
    📍 {region} / {district}<br>
    🚻 접근성 점수: {acc}<br>
    🛡️ 안전성 점수: {safe}
    """

    folium.CircleMarker(
        location=[lat, lon],
        radius=10 + acc,
        color=get_color(acc),
        fill=True,
        fill_opacity=0.7,
        popup=folium.Popup(popup_text, max_width=300)
    ).add_to(marker_cluster)

# 6. 지도 저장
# restroom_map.save('restroom_map_clean.html')



## 위험 지점 찾기
# 1. 좌표 기반 지역 분류 함수 (정밀화)
def classify_region_by_latlon(lat, lon):
    if 33 < lat < 34.5 and 126 < lon < 127.2:
        return '제주도'
    elif 34.8 < lat < 35.4 and 128.8 < lon < 129.3:
        return '부산'
    elif 37.4 < lat < 37.7 and 126.8 < lon < 127.2:
        return '서울'
    else:
        return '기타'

# 2. 데이터 정제 및 점수 정리
df_map = df.dropna(subset=['latitude', 'longitude']).copy()
df_map['accessibility_score'] = df_map['accessibility_score'].astype(float)
df_map['safety_score'] = df_map['safety_score'].astype(float)

# 3. 좌표 기반 지역명 생성 및 덮어쓰기
df_map['region_by_coord'] = df_map.apply(lambda row: classify_region_by_latlon(row['latitude'], row['longitude']), axis=1)

# 4. 좌표 유효 범위 필터링
valid_lat = (df_map['latitude'] > 33) & (df_map['latitude'] < 38)
valid_lon = (df_map['longitude'] > 124) & (df_map['longitude'] < 132)
df_map = df_map[valid_lat & valid_lon].copy()

# 5. 지역 불일치 제거
df_clean = df_map[df_map['region'] == df_map['region_by_coord']].copy()

# 6. 위험 여부 컬럼 생성
df_clean['is_risky'] = (df_clean['accessibility_score'] < 2.0) & (df_clean['safety_score'] < 1.5)

# 7. 위험 지점 필터링
risk_df = df_clean[df_clean['is_risky']].copy()

# 접근성과 안전성이 모두 0.0인 지점만 추출
critical_points = df_clean[
    (df_clean['accessibility_score'] == 0.0) &
    (df_clean['safety_score'] == 0.0)
]

# 8. 위험 비율 계산
risk_ratio = df_clean.groupby('region_by_coord')['is_risky'].mean().round(3)
risk_ratio = risk_ratio[risk_ratio.index != '기타']
# print("지역별 위험 비율:")
# print(risk_ratio)

# 9-1. 위험 지점 지도 생성
risk_map = folium.Map(location=[36.0, 127.5], zoom_start=6)
risk_cluster = MarkerCluster().add_to(risk_map)

for _, row in risk_df.iterrows():
    name = row.get('toilet_name') or row.get('address_road', '주소 없음')
    region = row.get('region_by_coord', '지역 없음')
    district = row.get('district', '구 정보 없음')
    acc = row['accessibility_score']
    safe = row['safety_score']

    popup_text = f"""
    <b>{name}</b><br>
    📍 {region} / {district}<br>
    🚻 접근성 점수: {acc}<br>
    🛡️ 안전성 점수: {safe}
    """

    folium.Marker(
        location=[row['latitude'], row['longitude']],
        popup=folium.Popup(popup_text, max_width=300),
        icon=folium.Icon(color='red', icon='exclamation-sign')
    ).add_to(marker_cluster)

# risk_map.save('risk_restroom_map.html')

# 9-2. 최우선 개선 대상 지도 (critical_points 기준)
critical_map = folium.Map(location=[36.0, 127.5], zoom_start=6)
critical_cluster = MarkerCluster().add_to(critical_map)

for _, row in critical_points.iterrows():
    name = row.get('toilet_name') or row.get('address_road', '주소 없음')
    region = row.get('region', '지역 없음')
    district = row.get('district', '구 정보 없음')
    acc = row['accessibility_score']
    safe = row['safety_score']

    popup_text = f"""
    <b>{name}</b><br>
    📍 {region} / {district}<br>
    🚻 접근성 점수: {acc}<br>
    🛡️ 안전성 점수: {safe}
    """

    folium.Marker(
        location=[row['latitude'], row['longitude']],
        popup=folium.Popup(popup_text, max_width=300),
        icon=folium.Icon(color='darkred', icon='exclamation-sign')
    ).add_to(marker_cluster)

# critical_map.save('critical_points_map.html')

# 10. 지역별 위험도 요약
risk_summary = risk_df.groupby('region_by_coord')[['accessibility_score', 'safety_score']].mean().round(2)
# print("\n지역별 위험도 요약:")
# print(risk_summary)

# 11. district_summary 보완
district_summary = (
    df_clean.groupby(['region', 'district'], dropna=False)[['accessibility_score', 'safety_score']]
    .mean()
    .round(2)
    .reset_index()
)

# 12. 위험 비율 시각화

# 위험 비율 기준으로 정렬
risk_ratio_sorted = risk_ratio.sort_values(ascending=False)

# 빨강 계열 색상 리스트 (위험도 높은 순서대로 진하게)
colors = ['#8B0000', '#CD5C5C', '#FA8072']

# 시각화
# plt.figure(figsize=(8, 5))
# sns.barplot(x=risk_ratio_sorted.index, y=risk_ratio_sorted.values, palette=colors)
# plt.title('지역별 위험 화장실 비율', fontsize=16)
# plt.ylabel('<위험 비율>')
# plt.xlabel('<지역>')
# plt.ylim(0, 1)
# plt.tight_layout()
# plt.show()

# 13. 위험 구 추출
low_access = district_summary[district_summary['accessibility_score'] == 0.00]
low_safety = district_summary[district_summary['safety_score'] <= 0.30]
critical_zones = district_summary[
    (district_summary['accessibility_score'] == 0.00) &
    (district_summary['safety_score'] <= 0.30)
]

# print("접근성·안전성 모두 낮은 구 (최우선 개선 대상):")
# print(critical_points['region'].value_counts())

# print("\n접근성·안전성 모두 낮은 지점 (최우선 개선 대상):")
# print(critical_points[['region', 'district', 'address_road', 'accessibility_score', 'safety_score']].reset_index(drop=True))


'''
해석
- 서울 은평구처럼 일부 지점은 극단적 위험 상태지만 구 전체 평균이 0.0이 아니기 때문에 critical_zones에는 안 잡힘
- critical_points는 실제 위험 지점을 정확히 포착하기 때문에 정책 우선순위나 현장 개선에 훨씬 유용함

의미 있는 결론
- 서울·부산에도 위험 지점은 존재한다
- 제주도는 위험 지점 비율이 높고, 평가 누락도 많다
- critical_points 기준이 더 현실적이고 정밀한 분석을 가능하게 한다
'''

'''
✅ 요약 정리
- 데이터 오류: 주소와 좌표 불일치 12건 → 지도 왜곡 원인
- 가장 위험한 지역: 부산 (접근성·안전성 모두 낮고 위험 비율 높음)
- 가장 안전한 구: 서울 영등포구 (접근성·안전성 모두 1.0)

- 접근성 + 안전성 모두 0점인 최우선 개선 대상인 곳은 : 서울(9곳), 부산(5곳)
- 서울은 용산구와 압구정로 일대에서 집중적으로 위험 지점이 나타남
- 부산은 기장지구대, 부산진구 일대, 수영구 등에서 위험 지점이 분포
- 제주도는 전체 접근성은 서울과 같았지만, 위험지점 접근성은 0.08로 가장 낮음

🧠 해석
- 부산은 전체적으로 위험 비율이 높지만, 서울은 특정 도로·구간에 위험 지점이 집중되어 있음
- 특히 서울의 경우 **용산구 주요 도로(청파로, 한강대로, 이촌로 등)**에서
접근성과 안전성 모두 전무한 공중화장실이 다수 발견됨
- 제주도는 겉보기는 양호해 보이나, 실제는 격차 심함 → 불균형 심각

✅ 정책적 시사점
- 서울은 “지점 수” 기준으로 개선 대상이 더 많음
- 부산은 “전체 비율” 기준으로 위험도가 더 높음
- 제주도는 "위험지점 접근성" 기준으로 불균형이 가장 높음

따라서:
- 서울: 위험 지점 수는 많지만, 전체적으로는 양호 → 지점 단위 집중 개선
- 부산: 위험 비율이 높고 평균 점수도 낮음 → 구 전체 인프라 개선
- 제주도: 전체 평균은 높지만 위험 지점의 접근성은 전국 최저 → 불균형 해소 중심 개선
'''

'''
✅ 요약 정리
- 데이터 오류: 주소와 좌표 불일치 12건 → 지도 왜곡 원인
- 가장 위험한 지역: 부산 (위험 비율 0.42, 평균 접근성 1.3, 안전성 1.1)
- 가장 안전한 구: 서울 영등포구 (접근성·안전성 모두 1.0)

- 접근성과 안전성이 모두 0점인 최우선 개선 대상 지점 수 (critical_points 기준):  
  → 전국 총 1,210개 지점  
  → 부산: 726곳 / 서울: 438곳 / 제주도: 46곳

- 서울은 용산구와 압구정로 일대에서 집중적으로 위험 지점이 나타남
- 부산은 기장지구대, 부산진구 일대, 수영구 등에서 위험 지점이 분포
- 제주도는 전체 평균 접근성은 서울과 같지만, 위험 지점의 접근성 평균은 0.08로 전국 최저 → 격차 심각

🧠 해석
- 부산은 위험 지점 수가 가장 많고, 전체 위험 비율도 높기 때문에 구 단위 인프라 개선이 필요함
- 서울은 위험 지점 수가 두 번째로 많지만, 전체 평균은 양호 → 특정 도로·구간에 집중되어 있어 지점 단위 개선이 효과적
- 제주도는 위험 지점 수는 적지만, 전체 지점 대비 비율이 높고 위험 지점 접근성 점수가 극단적으로 낮아 불균형 해소 중심의 개선이 필요함

✅ 정책적 시사점
- 부산: 위험 비율이 높고 평균 점수도 낮음 → 구 전체 인프라 개선
- 서울: 위험 지점 수는 많지만 전체적으로는 양호 → 지점 단위 집중 개선
- 제주도: 전체 평균은 높지만 위험 지점의 접근성은 전국 최저 → 불균형 해소 중심 개선
'''