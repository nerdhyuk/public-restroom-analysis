import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import re
import folium
from folium.plugins import MarkerCluster
from collections import defaultdict
import warnings

warnings.simplefilter("ignore")

# 파일 경로
path = 'C:/Users/anton/restroom_data/'

# 데이터 불러오기 (출처 : 공공데이터포털 - 지방행정인허가데이터개방)
seoul_df = pd.read_excel(path + '서울_공중화장실정보.xlsx')
busan_df = pd.read_excel(path + '부산_공중화장실정보.xlsx')
jeju_df = pd.read_excel(path + '제주도_공중화장실정보.xlsx')

# 데이터 구조 확인
# seoul_df.info()


# 주소 통합 (도로명 + 지번 주소)
def combine_address(row):
    road = str(row.get('address_road', '')).strip()
    lot = str(row.get('address_lot', '')).strip()
    return f"{road} {lot}".strip()

# 컬럼명 영문화
rename_dict = {
    '화장실명': 'toilet_name',
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
df.loc[df['region'].isin(['서울', '부산']), 'district'] = df.loc[df['region'].isin(['서울', '부산']), 'full_address'].apply(
    extract_gu)
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
    '서울': '#FF6347',
    '부산': '#4682B4',
    '제주도': '#53B9A9'
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
df_zero_access = df[df['accessibility_score'] == 0]
# print(df_zero_access['safety_score'].value_counts())

# 안전성 점수 분포 집계
score_counts = df_zero_access['safety_score'].value_counts().sort_index()


''' 시각화 '''
# scores = score_counts.index.tolist()
# counts = score_counts.values.tolist()
# def get_score_color(score):
#     color_map = {
#         0: '#FF6347',
#         1: '#53B9A9',
#         2: '#4682B4',
#         3: '#9370DB'
#     }
#     return color_map.get(score, '#999999')  # 예외 처리용
#
# # 그래프 그리기
# plt.figure(figsize=(10, 6))
# for i, (score, count) in enumerate(zip(scores, counts)):
#     plt.bar(x=i, height=count, color=get_score_color(score))
#     plt.text(i, count + 10, str(count), ha='center', va='bottom', fontsize=10)
#
# # 축 설정
# plt.xticks(ticks=range(len(scores)), labels=[str(score) for score in scores], fontsize=11)
# plt.yticks(fontsize=11)
# plt.xlabel('<안전성 점수>', fontsize=12)
# plt.ylabel('<공중화장실 수>', fontsize=12)
# plt.title('접근성 점수 0인 지점의 안전성 점수 분포', fontsize=16, pad=10)
# plt.tight_layout()
# plt.show()


'''
※ 그래프 해석
1. 첫 번째 막대 (안전성 점수 0)
- 2,233개 지점은 접근성도 없고 안전성도 없음
- 여전히 가장 위험한 상태
- 기본적인 인권과 안전이 동시에 결핍된 공간

2. 두 번째 막대 (안전성 점수 1)
- 1,053개 지점은 접근성은 없지만 안전성은 일부 갖춤
- 취약하지만 개선 여지 있음
- 최소한의 안전시설이 존재할 가능성

3. 세 번째 막대 (안전성 점수 2)
- 1,060개 지점은 접근성은 없지만 안전성은 상대적으로 확보됨
- 이는 시설 개선이 부분적으로 이루어지고 있다는 증거
- 접근성은 미비하지만 CCTV, 비상벨 등은 설치된 사례가 존재

4. 네 번째 막대 (안전성 점수 3)
- 271개 지점은 접근성은 없지만 안전성은 높음
- 예외적이지만 긍정적인 사례
- 안전 중심의 개선이 먼저 이루어진 곳일 가능성

※ 이 현상이 의미하는 것
1. 접근성과 안전성은 완전히 함께 결핍되지는 않는다
- 접근성은 없지만 안전성은 확보된 지점이 상당수 존재

2. 시설 개선이 부분적으로 이루어지고 있다
- 안전성 점수가 2점 이상인 지점이 1,300개 이상 존재
- 이는 안전 중심의 개선이 먼저 이루어진 정책 흐름을 반영할 수 있음

3. 정책 우선순위 설정이 더 정교해질 수 있다
- 단순히 접근성 0 + 안전성 ≤ 1만 보는 게 아니라 접근성 0 + 안전성 2~3인 지점은 접근성 중심 개선 대상으로 분류 가능
- 반대로 접근성 0 + 안전성 0~1인 지점은 이중 취약 지점으로 우선 개선 필요


※ 이 표가 주는 인사이트
- 접근성과 안전성 모두 부족한 지점이 전체적으로 많다 → 시설 개선이 시급한 지점들이 많다는 뜻
- 우선 개선 대상 지역을 선정할 수 있는 근거 자료 → 지자체나 구청에 정책 제안할 때 활용 가능

📌 정책 제안에 활용할 수 있는 메시지
- “접근성 점수가 0인 지점 중에서도 안전성 점수가 높은 사례가 존재한다는 것은, 
시설 개선이 안전 중심으로 먼저 이루어졌다는 흐름을 보여줍니다.
이제는 접근성 중심의 개선이 병행되어야 할 시점입니다.”
- “접근성과 안전성 모두 결핍된 지점은 여전히 3,000개 이상 존재하며, 
이중 취약 지점에 대한 우선 개선이 시민 체감도를 높이는 핵심 전략이 될 수 있습니다.”
'''


# 서울/부산 위험지점 추출
metro_risk = df[
    (df['region'].isin(['서울', '부산'])) &
    (df['accessibility_score'] == 0) &
    (df['safety_score'] <= 1)
    ].copy()

# 서울/부산 구별 위험지점 개수 출력
top_districts = (
    metro_risk.groupby(['region', 'district'])
    .size()
    .reset_index(name='count')
    .sort_values(by='count', ascending=False)
    .head(10)
)
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
jeju_risk_summary['region'] = '제주도'

# 제주 지역별 위험지점 개수 출력
district_counts = jeju_risk['district'].value_counts()
# print(district_counts)


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
    '서울': '#FF6F61',
    '부산': '#4A90E2',
    '제주도': '#53B9A9'
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
# plt.title('위험 지점 공중화장실 지역 TOP 10 (서울/부산) + 제주도', fontsize=17)
# plt.xlabel('<위험 지점 수>', fontsize=12)
# plt.ylabel('<지역>', fontsize=12)
# plt.yticks(fontsize=12)
# plt.legend(title='지역구분', fontsize=12, title_fontsize=12)
# plt.tight_layout()
# for container in ax.containers:
#     ax.bar_label(container, fmt='%d', label_type='edge', padding=3, fontsize=12)
# plt.show()


'''
※ 요약 문장
서울·부산·제주 지역의 공중화장실 중 접근성과 안전성이 모두 낮은 지점은 일부 구에 집중되어 있으며,
특히 서울의 서초구, 양천구, 동대문구 등은 위험 지점 수가 가장 많았다.
부산에서는 해운대구가 가장 많은 위험 지점을 기록했으며,
제주도는 서귀포시가 제주시보다 더 많은 취약 지점을 보유하고 있어 도심과 관광지를 포함한 전반적인 시설 개선이 요구된다.

※ 정책 제안 문구
접근성과 안전성이 모두 결여된 공중화장실은 시민의 기본 권리와 안전을 동시에 위협하는 구조적 사각지대입니다.
서울·부산의 상위 10개 구와 제주도의 주요 지역을 대상으로 우선 개선 사업을 추진하고,
장애인·노약자·영유아 보호를 위한 시설 확충과 안전 인프라(비상벨, CCTV 등) 설치를 병행해야 합니다.
'''


# 기저귀교환대 설치 여부
diaper_counts = df['has_diaper_table'].fillna(0).value_counts().sort_index()
diaper_labels = ['미설치', '설치']
diaper_colors = ['lightcoral', 'mediumseagreen']

# CCTV 설치 여부
cctv_counts = df['has_cctv'].fillna(0).value_counts().sort_index()
cctv_labels = ['미설치', '설치']
cctv_colors = ['mediumpurple', 'orange']

# 비상벨 설치 여부
bell_counts = df['emergency_bell_installed'].fillna(0).value_counts().sort_index()
bell_labels = ['미설치', '설치']
bell_colors = ['#4A90E2', 'gold']

def make_autopct(fontsize):
    def my_autopct(pct):
        return f'{pct:.1f}%'  # 퍼센트 포맷
    return lambda pct: f'{my_autopct(pct)}'  # 람다로 반환

def format_pie_chart(ax, wedges, texts, autotexts, title):
    ax.set_title(title, fontsize=16, pad=0)
    for text in texts:
        text.set_fontsize(11)
    for autotext in autotexts:
        autotext.set_fontsize(14)

fig, axes = plt.subplots(1, 3, figsize=(12, 4))

# 기저귀교환대
wedges1, texts1, autotexts1 = axes[0].pie(
    diaper_counts, labels=diaper_labels, autopct=make_autopct(14),
    startangle=90, colors=diaper_colors
)
format_pie_chart(axes[0], wedges1, texts1, autotexts1, '<기저귀교환대 설치 여부>')

# CCTV
wedges2, texts2, autotexts2 = axes[1].pie(
    cctv_counts, labels=cctv_labels, autopct=make_autopct(14),
    startangle=90, colors=cctv_colors
)
format_pie_chart(axes[1], wedges2, texts2, autotexts2, '<CCTV 설치 여부>')

# 비상벨
wedges3, texts3, autotexts3 = axes[2].pie(
    bell_counts, labels=bell_labels, autopct=make_autopct(12),
    startangle=90, colors=bell_colors
)
format_pie_chart(axes[2], wedges3, texts3, autotexts3, '<비상벨 설치 여부>')

# plt.tight_layout(pad=0)
# plt.show()


'''
※ 기저귀교환대 설치 여부
- 설치: 25.6% / 미설치: 74.4%
- 4곳 중 3곳 이상이 기저귀교환대를 갖추지 않음 → 영유아 동반 이용자에 대한 배려 부족
- 가족 단위 외출 시 불편을 초래하고, 공공시설의 포용성이 떨어짐

※ CCTV 설치 여부
- 설치: 31.6% / 미설치: 68.4%
- 3곳 중 2곳 이상이 CCTV 미설치 상태 → 야간·취약계층 보호에 취약
- 범죄 예방 및 심리적 안정 효과가 기대되는 시설임에도 불구하고 설치율이 낮아 
  기본적인 안전 인프라로서의 역할을 충분히 수행하지 못하는 상황

※ 비상벨 설치 여부
- 설치: 51.6% / 미설치: 48.4%
- 절반 이상이 비상벨을 갖추고 있지만, 여전히 거의 절반 가까운 시설이 미설치 상태 → 긴급 상황 대응 인프라가 불충분하다는 신호
- 특히 여성·노약자·아동 이용자에게 심리적 불안 요소가 될 수 있음

🧩 종합 인사이트
- 공중화장실의 편의성과 안전성 모두에서 시설 불균형이 존재함
- 특히 기저귀교환대는 보급률이 매우 낮아 개선 우선순위로 고려될 필요가 있음
- CCTV는 범죄 예방과 취약계층 보호 측면에서 필수적이나 설치율이 낮아, 기본 안전 인프라로서의 기능을 충분히 수행하지 못함
- 비상벨은 절반 이상 설치되어 있지만, 전면 확대 설치가 필요한 상황이며, 남성 공간 등 사각지대 보완도 필요
'''


# 설치 여부 컬럼 리스트
install_cols = ['has_diaper_table', 'has_cctv', 'emergency_bell_installed']
for col in install_cols:
    df[col] = df[col].map({'Y': 1, 'N': 0}).fillna(0).astype(int)

# 시설별 누락률 분석
missing_summary = df[install_cols].apply(lambda x: (x == 0).sum())
total_count = len(df)
missing_rate = (missing_summary / total_count * 100).round(1)

missing_df = pd.DataFrame({
    '시설명': ['기저귀교환대', 'CCTV','비상벨'],
    '미설치 수': missing_summary.values,
    '미설치율 (%)': missing_rate.values
})
# print("시설별 누락률 분석 결과:")
# print(missing_df)

# 비상벨 설치 장소 분석
installed_bell = df[df['emergency_bell_installed'] == 1]
location_counts = installed_bell['emergency_bell_location'].value_counts()
location_df = location_counts.reset_index()
location_df.columns = ['설치 장소', '설치 수']
# print("비상벨 설치 장소 분석 결과:")
# print(location_df)


'''
※ 시설별 누락률 분석 해석
전체 공중화장실 중
- 기저귀교환대는 74.4%가 미설치 (4곳 중 3곳 이상이 미설치)
- CCTV는 68.4%가 미설치 (3곳 중 2곳 이상이 미설치)
- 비상벨은 48.4%가 미설치 (절반 가까이 미설치 상태)
    → 이는 특히 영유아 동반 이용자와 야간·취약계층 이용자에게 불편과 불안 요소를 유발할 수 있으며,
      편의성과 안전성 모두에서 시설 보급률이 낮은 상황임을 보여준다.

※ 비상벨 설치 장소 분석 해석
비상벨이 설치된 4,831개소 중
- 가장 많은 설치 유형은 남자화장실+여자화장실 (1,306개소)
- 다음으로 장애인+남자+여자 복합 설치 (1,251개소)
- 단독 설치는 여자화장실 (1,151개소), 장애인화장실 (296개소) 등으로 나타났다.
    → 이는 비상벨이 여성·장애인 중심으로 설치되는 경향을 보여주며, 사회적 약자 보호 목적이 반영된 배치로 해석된다.
      하지만 남성화장실 단독 설치는 9개소에 불과해 모든 이용자를 포괄하는 균형 잡힌 안전 인프라 확대가 필요하다.

🧩 복합 설치가 많지만, 남성 공간은 사각지대
📌 여성·장애인 중심 설치는 긍정적이나, 남성·공용 공간도 보완 필요

※ 보고서에 넣을 수 있는 요약 문구
“기저귀교환대는 전체의 74.4%가 미설치 상태로, 공중화장실의 편의성 측면에서 가장 시급한 개선 대상이다.
비상벨은 여성·장애인 공간에 집중 설치되어 있으나, 남성 공간은 설치 비율이 현저히 낮아 균형 있는 안전 인프라 확대가 필요하다.”
'''

'''
✍️ 보고서 결론 정리 문단
본 분석을 통해 서울·부산·제주의 공중화장실은 접근성과 안전성 측면에서 시설 보급률의 불균형이 존재함을 확인하였다.
특히 기저귀교환대는 전체의 74.4%가 미설치 상태로, 영유아 동반 이용자에 대한 배려가 부족한 상황이다.
비상벨은 여성·장애인 공간에 집중 설치되어 있으나, 남성 및 공용 공간은 사각지대로 남아 있어 전면적이고 균형 잡힌 안전 인프라 확대가 필요하다.

이에 따라 향후 정책 제안으로는
- 사회적 약자 중심의 편의시설 확대
- 야간·취약계층 보호를 위한 CCTV 및 비상벨 설치 강화
- 시설 설치 기준의 지역별 표준화 를 제시하며,
후속 연구로는 민원 데이터 연계 분석과 이용자 만족도 기반 정성적 평가가 필요하다.
'''



### 전체 데이터 갯수 vs 매핑 누락 데이터
## 위도/경도 누락된 데이터값이 많음
# 1. 좌표 기반 지역 분류 함수
def classify_region_by_latlon(lat, lon):
    if 33 < lat < 34.5 and 126 < lon < 127.2:
        return '제주도'
    elif 34.8 < lat < 35.4 and 128.8 < lon < 129.3:
        return '부산'
    elif 37.4 < lat < 37.7 and 126.8 < lon < 127.2:
        return '서울'
    else:
        return '기타'

# 2. 전체 데이터 지역별 개수 (주소 기반)
region_counts_total = df['region'].value_counts()[['서울', '부산', '제주도']]

# 3. 좌표 기반 지역 분류 및 정제
df_map = df.dropna(subset=['latitude', 'longitude']).copy()
df_map['region_by_coord'] = df_map.apply(lambda row: classify_region_by_latlon(row['latitude'], row['longitude']), axis=1)

# 4. 주소 기반 지역과 좌표 기반 지역이 일치하는 지점만 필터링
df_matched = df_map[df_map['region'] == df_map['region_by_coord']].copy()

# 5. 매핑된 지역별 개수
region_counts_mapped = df_matched['region'].value_counts()[['서울', '부산', '제주도']]

# 6. 차이 계산
region_diff = region_counts_total - region_counts_mapped

# 7. 결과 출력
# print("📊 지역별 전체 화장실 수 (주소 기반):")
# print(region_counts_total)
# print("\n📍 좌표 기반으로 매핑된 화장실 수:")
# print(region_counts_mapped)
# print("\n⚠️ 매핑되지 못한 수량 (누락 또는 오류):")
# print(region_diff)


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

# 중복 좌표수 확인 (451개)
duplicate_coords = df_map.groupby(['latitude', 'longitude']).size()
duplicate_coords = duplicate_coords[duplicate_coords > 1]
# print("중복 좌표 수:", len(duplicate_coords))

# 3. 지도 생성
restroom_map = folium.Map(location=[36.0, 127.5], zoom_start=7)
marker_cluster = MarkerCluster().add_to(restroom_map)

# 4. 색상 함수 (접근성 점수 기준)
def get_color(score):
    if score >= 3:
        return 'green'
    elif score >= 2:
        return 'orange'
    else:
        return 'red'

# 5. 좌표 기준으로 그룹핑 (중복 위치 통합)
grouped = defaultdict(list)
for _, row in df_map.iterrows():
    key = (row['latitude'], row['longitude'])
    grouped[key].append(row)

# 6. 마커 생성
for (lat, lon), rows in grouped.items():
    popup_entries = []

    for row in rows:
        name = row.get('toilet_name') or row.get('address_road', '주소 없음')
        region = row.get('region_by_coord', '지역 없음')
        district = row.get('district', '구 정보 없음')
        address = row.get('full_address', '주소 없음')
        acc = row.get('accessibility_score', 0)
        safe = row.get('safety_score', 0)

        entry = f"""
        <b>{name}</b><br>
        📍 {region} / {district}<br>
        📫 주소: {address}<br>
        🚻 접근성 점수: {acc:.1f}<br>
        🛡️ 안전성 점수: {safe:.1f}<br><hr>
        """
        popup_entries.append(entry)

    popup_text = "".join(popup_entries)

    # 평균 접근성 점수로 색상 결정
    avg_acc = sum([r.get('accessibility_score', 0) for r in rows]) / len(rows)
    color = get_color(avg_acc)

    popup_text = "".join(popup_entries)

    popup_html = f"""
    <div style="max-height:300px; overflow-y:auto;">
    {popup_text}
    </div>
    """

    folium.CircleMarker(
        location=[lat, lon],
        radius=6 + len(rows) * 2,
        color=color,
        fill=True,
        fill_opacity=0.7,
        popup=folium.Popup(popup_html, max_width=350)
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

# 6-1. 위험 유형 분류
df_clean['risk_type'] = df_clean.apply(
    lambda row: '접근성만 낮음' if row['accessibility_score'] < 2.0 and row['safety_score'] >= 1.5 else
                '안전성만 낮음' if row['accessibility_score'] >= 2.0 and row['safety_score'] < 1.5 else
                '둘 다 낮음' if row['is_risky'] else '양호',
    axis=1
)
# print(df_clean['risk_type'].value_counts())

# 6-2. 위험 유형별 개선 전략 추천
def recommend_strategy(row):
    if row['risk_type'] == '접근성만 낮음':
        return '진입로 개선, 장애인 접근성 강화'
    elif row['risk_type'] == '안전성만 낮음':
        return '조명, CCTV, 주변 환경 정비'
    elif row['risk_type'] == '둘 다 낮음':
        return '종합 인프라 개선 필요'
    else:
        return '유지관리 중심'

df_clean['recommendation'] = df_clean.apply(recommend_strategy, axis=1)

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

# 9. 위험 지점 지도 생성
risk_map = folium.Map(location=[36.0, 127.5], zoom_start=7)
risk_cluster = MarkerCluster().add_to(risk_map)

grouped = defaultdict(list)
for _, row in risk_df.iterrows():
    key = (row['latitude'], row['longitude'])
    grouped[key].append(row)

# 10.마커 생성
for (lat, lon), rows in grouped.items():
    seen_names = set()
    popup_entries = []

    for row in rows:
        name = row.get('toilet_name') or row.get('address_road', '이름 없음')
        if name in seen_names:
            continue  # 이미 본 이름이면 건너뛰기
        seen_names.add(name)

        region = row.get('region_by_coord', '지역 없음')
        district = row.get('district', '구 정보 없음')
        acc = row['accessibility_score']
        safe = row['safety_score']
        strategy = row.get('recommendation', '전략 없음')

        entry = f"""
        <b>🚻 {name}</b><br>
        📍 지역: {region} / {district}<br>
        📫 주소: {row.get('full_address', '주소 없음')}<br>
        🧭 접근성 점수: {acc:.1f}<br>
        🛡️ 안전성 점수: {safe:.1f}<br>
        🛠️ 개선 전략: {strategy}<br><hr>
        """
        popup_entries.append(entry)

    popup_text = "".join(popup_entries)

    popup_html = f"""
    <div style="max-height:300px; overflow-y:auto;">
    {popup_text}
    </div>
    """

    folium.Marker(
        location=[lat, lon],
        popup=folium.Popup(popup_html, max_width=350),
        icon=folium.Icon(color='red', icon='exclamation-sign')
    ).add_to(risk_cluster)

# 11.지도 저장
# risk_map.save('risk_restroom_map.html')


'''
📌 분석 요약
- 위도/경도 기반 매핑은 시각적으로 유의미한 부분적 인사이트를 제공하지만
- 서울·제주도 등 주요 지역에서 좌표 누락률이 너무 높아
- 전체 데이터를 대표하거나 정책적 결론을 도출하기엔 한계가 있음

따라서
“본 지도 시각화는 위도·경도 정보를 기반으로 한 부분적 분석이며,
서울과 제주도 지역의 좌표 누락률이 높아 전체 흐름을 반영하기엔 제한적입니다.
따라서 지도는 공간적 경향 파악용으로 활용하고,
전체 분석은 주소 기반 통계와 병행하여 해석하는 것이 필요합니다.”
'''