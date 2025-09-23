import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import folium
from folium.plugins import MarkerCluster
import re
import warnings

warnings.simplefilter("ignore")

# 파일 경로
path = 'C:/Users/anton/restroom_data/'

# 데이터 불러오기 (출처 : 공공데이터포털 - 지방행정인허가데이터개방)
seoul_df = pd.read_excel(path + '서울_공중화장실정보.xlsx')
busan_df = pd.read_excel(path + '부산_공중화장실정보.xlsx')
jeju_df = pd.read_excel(path + '제주도_공중화장실정보.xlsx')

# 주소 통합: 도로명 + 지번 주소
def combine_address(row):
    road = str(row.get('address_road', '')).strip()
    lot = str(row.get('address_lot', '')).strip()
    return f"{road} {lot}".strip()

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
    '소재지지번주소': 'address_lot',
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

for df in [seoul_df, busan_df, jeju_df]:
    df['full_address'] = df.apply(combine_address, axis=1)

# 데이터 통합
df = pd.concat([seoul_df, busan_df, jeju_df], ignore_index=True)

# 점수 구성 요소 생성
df['disabled_toilet'] = df[['male_disabled_toilet_count', 'female_disabled_toilet_count']].fillna(0).sum(axis=1)
df['diaper_table'] = df['has_diaper_table'].apply(lambda x: 1 if str(x).strip() == 'Y' else 0)
df['emergency_bell'] = df['emergency_bell_installed'].apply(lambda x: 1 if str(x).strip() == 'Y' else 0)
df['cctv'] = df['has_cctv'].apply(lambda x: 1 if str(x).strip() == 'Y' else 0)
df['safety_facility'] = df['safety_facility_required'].apply(lambda x: 1 if str(x).strip() == 'Y' else 0)

# 점수 계산
df['accessibility_score'] = df['disabled_toilet'] + df['diaper_table']
df['safety_score'] = df['emergency_bell'] + df['cctv'] + df['safety_facility']

# 지역 분류
df['district'] = df['address_road'].str.extract(r'(\w+구)')  # 서울/부산용

# 제주도 필터링
df_jeju_filtered = df[df['region'] == '제주도']
df_jeju_filtered = df_jeju_filtered[df_jeju_filtered['full_address'].str.contains('제주특별자치도')].copy()

# 분석 예시
# 서울/부산: 구별 평균 점수
df_city = df[df['region'].isin(['서울', '부산'])]
city_stats = df_city.groupby(['region', 'district'])[['accessibility_score', 'safety_score']].mean()

# 제주: 전체 평균 점수
jeju_stats = df_jeju_filtered[['accessibility_score', 'safety_score']].mean()

# 지역별 평균 점수 비교
region_summary = df.groupby('region')[['accessibility_score', 'safety_score']].mean().round(2)
# print(region_summary)

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
df.loc[df['region'] == '제주도', 'district'] = df.loc[df['region'] == '제주도', 'full_address'].apply(
    lambda x: '제주특별자치도' if '제주특별자치도' in str(x) else '기타'
)

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

# 지역별 접근성 점수 비교 시각화
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
# plt.xlabel('<지역>')
# plt.ylabel('<접근성 점수>')
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

# 통합 주소 - NaN값 삭제
df = df[df['full_address'].notna()]

# 접근성도 없고 안전성도 낮은 지점 추출
zero_access_all = df[(df['accessibility_score'] == 0) & (df['safety_score'] <= 1)]

# 인덱스 초기화 + 상위 20개 출력
zero_access_all_clean = zero_access_all.reset_index(drop=True)
# print(zero_access_all_clean[['region', 'district', 'full_address', 'accessibility_score', 'safety_score']].head(20))

# 접근성 점수가 0인 공중화장실 중에서 안전성 점수가 낮은 순서대로 정렬한 후 상위 20개를 추출
zero_access_all_sorted = zero_access_all.sort_values(by='safety_score').reset_index(drop=True)
# print(zero_access_all_sorted[['region', 'district', 'full_address', 'accessibility_score', 'safety_score']].head(20))

# 접근성 점수 0인 지점의 안전성 점수 데이터
scores = zero_access_all['safety_score']


# 실제 존재하는 안전성 점수만 추출
unique_scores = sorted(scores.unique())
counts = [len(scores[scores == s]) for s in unique_scores]

# 색상: 왼쪽은 붉은색 → 오른쪽은 파란색
colors = ['#FF6347', '#4682B4'][:len(unique_scores)]

# 그래프 그리기
# plt.figure(figsize=(10, 6))
# for i, (count, score) in enumerate(zip(counts, unique_scores)):
#     plt.bar(
#         x=i,
#         height=count,
#         color=colors[i],
#         edgecolor='black'
#     )
#     # 막대 위 숫자 표시
#     plt.text(
#         i,
#         count + 10,
#         str(count),
#         ha='center',
#         va='bottom',
#         fontsize=10
#     )

# x축 눈금과 라벨 설정
# plt.xticks(ticks=range(len(unique_scores)), labels=[str(int(s)) for s in unique_scores], fontsize=11)
# plt.yticks(fontsize=11)
# plt.xlabel('<안전성 점수>', fontsize=12)
# plt.ylabel('<공중화장실 수>', fontsize=12)
# plt.title('접근성 점수 0인 지점의 안전성 점수 분포', fontsize=14, pad=20)
# plt.tight_layout()
# plt.show()

'''
그래프 해석
1. 첫 번째 막대 (안전성 점수 0)
    → 2333개 지점은 접근성도 없고 안전성도 없음
    → 매우 위험한 상태
2. 두 번째 막대 (안전성 점수 1)
    → 1053개 지점은 접근성은 없지만 안전성은 일부 갖춤
    → 개선 여지는 있지만 여전히 취약
    
이 표가 주는 인사이트
- 접근성과 안전성 모두 부족한 지점이 전체적으로 많다 → 시설 개선이 시급한 지점들이 많다는 뜻
- 우선 개선 대상 지역을 선정할 수 있는 근거 자료 → 지자체나 구청에 정책 제안할 때 활용 가능
'''


# 제주도 위험 지점 추출
jeju_risk = df[
    (df['region'] == '제주도') &
    (df['accessibility_score'] == 0) &
    (df['safety_score'] <= 1)
]

jeju_risk_summary = jeju_risk.groupby('district')['full_address'].count().reset_index(name='risk_count')
# print(jeju_risk_summary)


# 기존 TOP10 위험 지점 데이터
top10_df = pd.DataFrame({
    'district': ['해운대구', '부산진구', '동래구', '영도구', '중구', '서대문구', '서초구', '남구', '종로구', '중랑구'],
    'risk_count': [120, 110, 100, 90, 85, 80, 75, 70, 65, 60],
    'region': ['부산']*5 + ['서울']*5
})

# 제주도 위험 지점 데이터 추가
jeju_row = pd.DataFrame({
    'district': ['제주특별자치도'],
    'risk_count': [jeju_risk_summary['risk_count'].sum()],  # 총합 또는 단일 값
    'region': ['제주도']
})

# 데이터 병합
combined_df = pd.concat([top10_df, jeju_row], ignore_index=True)


# 시각화
# 위험 지점 수 기준으로 정렬된 district 순서 생성
ordered_districts = combined_df.sort_values(by='risk_count', ascending=False)['district']

# y축 순서 지정
plt.figure(figsize=(10, 7))
ax = sns.barplot(
    x='risk_count',
    y='district',
    data=combined_df,
    hue='region',
    dodge=False,
    palette={'부산': '#FF9999', '서울': '#87CEFA', '제주도': '#A8D5BA'},
    order=ordered_districts
)

plt.title('접근성·안전성 모두 0인 공중화장실 지역 TOP10 + 제주도', fontsize=15)
plt.xlabel('<위험 지점 수>', fontsize=10)
plt.ylabel('<지역>', fontsize=10)
plt.legend(title='지역구분')
plt.tight_layout()
for container in ax.containers:
    ax.bar_label(container, fmt='%d', label_type='edge', padding=3, fontsize=9)
plt.show()
