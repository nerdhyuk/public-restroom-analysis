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

# 주소 통합 (도로명 + 지번 주소)
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

# 지역 분류 (서울/부산)
df['district'] = df['full_address'].str.extract(r'([가-힣]+구)')

# 제주도 필터링
df_jeju_filtered = df[df['region'] == '제주도']
df_jeju_filtered = df_jeju_filtered[df_jeju_filtered['full_address'].str.contains('제주특별자치도')].copy()


# 서울/부산 (구별 평균 점수)
df_city = df[df['region'].isin(['서울', '부산'])]
city_stats = df_city.groupby(['region', 'district'])[['accessibility_score', 'safety_score']].mean()

# 제주 (전체 평균 점수)
jeju_stats = df_jeju_filtered[['accessibility_score', 'safety_score']].mean()

## 지역별 평균 점수 비교
region_summary = df.groupby('region')[['accessibility_score', 'safety_score']].mean().round(2)
# print(region_summary)


# '구' 추출 함수 (서울/부산)
def extract_gu(address):
    if not isinstance(address, str):
        return None
    match = re.search(r'([가-힣]+구)\b', address)
    if match:
        gu = match.group(1)
        if gu in ['출입구', '입구', '출구']:
            return None
        return gu
    return None

# 'district' 컬럼 생성
df['district'] = None
df.loc[df['region'].isin(['서울', '부산']), 'district'] = df.loc[df['region'].isin(['서울', '부산']), 'full_address'].apply(extract_gu)
df.loc[df['region'] == '제주도', 'district'] = df.loc[df['region'] == '제주도', 'full_address'].apply(
    lambda x: '제주특별자치도' if '제주특별자치도' in str(x) else '기타'
)

# 서울, 부산 평균 점수 계산
mainland_summary = df[df['region'].isin(['서울', '부산'])] \
    .groupby('region')[['accessibility_score', 'safety_score']] \
    .mean().round(2).reset_index()

# 제주도 평균 점수 계산
jeju_summary = df[df['region'] == '제주도'][['accessibility_score', 'safety_score']] \
    .mean().round(2).to_frame().T
jeju_summary['region'] = '제주도'
jeju_summary = jeju_summary[['region', 'accessibility_score', 'safety_score']]

# 통합
region_summary = pd.concat([mainland_summary, jeju_summary], ignore_index=True)


''' 시각화 준비 '''
# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

# 색상 지정
region_colors = {
    '부산': '#FF9999',
    '서울': '#87CEFA',
    '제주도': '#A8D5BA'
}

# # 지역별 접근성 점수 비교 시각화
# plt.figure(figsize=(8, 5))
# ax = sns.barplot(
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
# for container in ax.containers:
#     ax.bar_label(container, fmt='%.2f', label_type='edge', padding=0, fontsize=10)
# plt.show()
#
#
# # 지역별 안전성 점수 비교 시각화
# plt.figure(figsize=(8, 5))
# ax = sns.barplot(
#     x='region',
#     y='safety_score',
#     hue='region',
#     data=region_summary,
#     palette=region_colors,
#     legend=False
# )
# plt.title('지역별 안전성 점수 비교', fontsize=16, pad=20)
# plt.xlabel('<지역>')
# plt.ylabel('<안전성 점수>')
# plt.xticks(fontsize=11)
# plt.yticks(fontsize=11)
# plt.tight_layout()
# for container in ax.containers:
#     ax.bar_label(container, fmt='%.2f', label_type='edge', padding=0, fontsize=10)
# plt.show()


# 접근성 점수 0인 지점 확인
district_summary = (
    df.groupby(['region', 'district'], dropna=False)[['accessibility_score', 'safety_score']]
    .mean()
    .round(2)
    .reset_index()
)

# 통합 주소 누락 제거
df = df[df['full_address'].notna()]

# 접근성도 없고 안전성도 낮은 지점 추출 (가장 취약한 공중화장실 후보군)
zero_access_all = df[(df['accessibility_score'] == 0) & (df['safety_score'] <= 1)]

# 접근성도 없고 안전성도 낮은 지점 상위 20개 출력
zero_access_all_clean = zero_access_all.reset_index(drop=True)
# print(zero_access_all_clean[['region', 'district', 'full_address', 'accessibility_score', 'safety_score']].head(20))

# 접근성 점수가 0인 공중화장실 중에서 안전성 점수가 낮은 순서대로 정렬한 후 상위 20개를 추출 (우선 개선 대상을 파악하기 위한 정렬)
zero_access_all_sorted = zero_access_all.sort_values(by='safety_score').reset_index(drop=True)
# print(zero_access_all_sorted[['region', 'district', 'full_address', 'accessibility_score', 'safety_score']].head(20))


# 접근성 점수 0인 지점의 안전성 점수 데이터
scores = zero_access_all['safety_score']

# 실제 존재하는 안전성 점수만 추출
unique_scores = [0, 1, 2]
counts = [len(scores[scores == s]) for s in unique_scores]


''' 시각화 '''
colors = ['#FF6347', '#4682B4', '#90EE90']

# # 그래프 그리기
# plt.figure(figsize=(10, 6))
# for i, (count, score) in enumerate(zip(counts, unique_scores)):
#     plt.bar(
#         x=i,
#         height=count,
#         color=colors[i],
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
# # x축 눈금과 라벨 설정
# plt.xticks(ticks=range(len(unique_scores)), labels=[str(int(s)) for s in unique_scores], fontsize=11)
# plt.yticks(fontsize=11)
# plt.xlabel('<안전성 점수>', fontsize=12)
# plt.ylabel('<공중화장실 수>', fontsize=12)
# plt.title('접근성 점수 0인 지점의 안전성 점수 분포', fontsize=14, pad=20)
# plt.tight_layout()
# plt.show()

'''
※ 그래프 해석
1. 첫 번째 막대 (안전성 점수 0)
    → 2333개 지점은 접근성도 없고 안전성도 없음
    → 매우 위험한 상태
    
2. 두 번째 막대 (안전성 점수 1)
    → 1053개 지점은 접근성은 없지만 안전성은 일부 갖춤
    → 개선 여지는 있지만 여전히 취약
    
3. 세 번째 막대 (안전성 점수 2)
    → 접근성 점수가 0인 공중화장실 중에서 안전성 점수가 2점 이상인 곳이 하나도 없다는 것은 단순한 우연이 아니라,
      구조적인 문제와 정책적 사각지대가 존재한다는 강력한 신호
      
※ 이 현상이 의미하는 것
1. 접근성과 안전성은 함께 결핍되는 경향이 있다
- 접근성 점수가 0이라는 건 장애인 화장실, 기저귀 교환대가 전혀 없다는 뜻
- 그런데 안전성 점수도 2점 이상이 없다는 건 → CCTV, 비상벨, 안전시설도 거의 없다는 것
- 즉, 기본적인 인권과 안전이 동시에 무시된 공간이라는 뜻

2. 시설 개선이 단편적으로 이뤄지고 있다
- 일부 화장실은 접근성은 없지만 안전성은 높을 수도 있어야 하는데
- 그런 사례가 전혀 없다는 건 → 시설 개선이 종합적이지 않고, 한쪽만 개선되거나 아예 방치된 경우가 많다는 것
3. 정책 우선순위 설정에 활용 가능

- 접근성 0 + 안전성 ≤ 1인 지점은 이중 취약 지점
- 이런 곳부터 우선적으로 개선해야 예산 대비 효과가 크고 → 시민 체감도도 높아질 수 있다
    
※ 이 표가 주는 인사이트
- 접근성 0인 지점에 안전성 2점이 하나도 없다는 건 가장 취약한 공중화장실들이 안전조차 확보되지 않았다는 구조적 문제를 보여주는 인사이트
- 접근성과 안전성 모두 부족한 지점이 전체적으로 많다 → 시설 개선이 시급한 지점들이 많다는 뜻
- 우선 개선 대상 지역을 선정할 수 있는 근거 자료 → 지자체나 구청에 정책 제안할 때 활용 가능
'''

# 서울/부산 위험 지점 추출
metro_risk = df[
    (df['region'].isin(['서울', '부산'])) &
    (df['accessibility_score'] == 0) &
    (df['safety_score'] <= 1)
].copy()

# 구별 위험 지점 개수 세기
top_districts = metro_risk['district'].value_counts().head(10)
# print(top_districts)


# 제주도 위험 지점 추출
jeju_risk = df[
    (df['region'].str.contains('제주')) &
    (df['accessibility_score'] == 0) &
    (df['safety_score'] <= 1)
].copy()

# 제주도 district 세분화 함수
def refine_jeju_district(address):
    address = str(address)
    if '제주시' in address:
        return '제주시'
    elif '서귀포시' in address:
        return '서귀포시'
    elif '제주특별자치도' in address:
        return '기타 제주'
    else:
        return '기타'

jeju_risk['district'] = jeju_risk['full_address'].apply(refine_jeju_district)
jeju_risk['region'] = '제주도'

jeju_risk_summary = jeju_risk.groupby('district')['full_address'].count().reset_index(name='risk_count')
jeju_risk_summary['region'] = jeju_risk_summary['district']


# 서울/부산 위험 지점 요약
metro_summary = metro_risk.groupby(['region', 'district'])['full_address'].count().reset_index(name='risk_count')

# 서울+부산 상위 10개만 추출
top10_metro = metro_summary.sort_values(by='risk_count', ascending=False).head(10)

# 제주도 위험 지점 요약
jeju_risk_summary = jeju_risk.groupby(['region', 'district'])['full_address'].count().reset_index(name='risk_count')

# 데이터 병합
combined_df = pd.concat([top10_metro, jeju_risk_summary], ignore_index=True)

# 정렬 기준
ordered_districts = combined_df.sort_values(by='risk_count', ascending=False)['district']


''' 시각화 '''
palette = {
    '부산': '#FF9999',
    '서울': '#87CEFA',
    '제주도': '#A8D5BA'
}

# plt.figure(figsize=(10, 7))
# ax = sns.barplot(
#     x='risk_count',
#     y='district',
#     data=combined_df,
#     hue='region',
#     dodge=False,
#     palette=palette,
#     order=ordered_districts
# )
# plt.title('접근성·안전성 모두 낮은 공중화장실 지역 TOP10 (서울/부산) + 제주도', fontsize=15)
# plt.xlabel('<위험 지점 수>', fontsize=11)
# plt.ylabel('<지역>', fontsize=11)
# plt.legend(title='지역구분')
# plt.tight_layout()
# for container in ax.containers:
#     ax.bar_label(container, fmt='%d', label_type='edge', padding=3, fontsize=9)
# plt.show()


'''
※ 요약 문장
서울·부산 지역의 공중화장실 중 접근성과 안전성이 모두 낮은 지점은 특정 구에 집중되어 있으며, 
특히 서초구, 양천구, 부산진구 등은 위험 지점 수가 가장 많았다. 
제주도 역시 제주시를 중심으로 취약 지점이 분포되어 있어, 도심권과 관광지 모두에서 시설 개선이 시급한 상황이다.

※ 정책 제안 문구
접근성과 안전성이 모두 결여된 공중화장실은 시민의 기본 권리와 안전을 동시에 위협하는 구조적 사각지대입니다.
서울·부산의 상위 10개 구와 제주도의 주요 지역을 대상으로 우선 개선 사업을 추진하고,
장애인·노약자·영유아 보호를 위한 시설 확충과 안전 인프라(비상벨, CCTV 등) 설치를 병행해야 합니다.

※ 강조 문구
“접근성 없는 화장실은 곧 안전도 없다”
“도심과 관광지 모두, 공공시설의 기본부터 다시 설계해야 할 때"
“위험 지점 수는 단순한 숫자가 아니라 시민의 불편과 불안의 총합입니다”
'''