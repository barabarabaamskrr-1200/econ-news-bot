import os
import requests
import feedparser
from google import genai
from google.genai import types

# 1. GitHub 비밀 금고(Secrets)에서 키 불러오기
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

client = genai.Client(api_key=GEMINI_API_KEY)

# 2. 국내외 5대 경제신문 RSS 수집 함수 (API 키 불필요, 완전 무료)
def get_econ_news():
    rss_sources = {
        "한국경제(경제/금융)": "https://www.hankyung.com/feed/economy",
        "매일경제(헤드라인)": "https://www.mk.co.kr/rss/30000001/",
        "서울경제(마켓/금융)": "https://m.sedaily.com/rss/finance",
        "파이낸셜뉴스(종합)": "https://www.fnnews.com/rss/r20/fn_realnews_all.xml",
        "WSJ/글로벌경제(영문)": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml" # 월스트리트저널 글로벌 마켓
    }
    
    news_list = []
    for paper_name, url in rss_sources.items():
        try:
            feed = feedparser.parse(url)
            # 신문사별로 가장 최신 핵심 기사 3개씩 추출 (총 15개 기사)
            for entry in feed.entries[:3]:
                title = entry.title
                summary = entry.get('description', '요약 없음')
                # HTML 태그 간단 제거 및 길이 조절
                summary = summary.replace('<p>', '').replace('</p>', '')[:200]
                link = entry.link
                news_list.append(f"[{paper_name}] 제목: {title}\n내용요약: {summary}\n원문링크: {link}")
        except Exception as e:
            print(f"{paper_name} 수집 오류 건너뜀: {e}")
            
    return "\n\n".join(news_list)

# 3. 제미나이 통합 분석 함수 (뉴스 5곳 + PDF 원문 + 직무/지역인재/단어장)
def analyze_with_gemini(news_text, pdf_url=None):
    prompt = f"""
    당신은 시중은행(KB국민, 신한, 하나, 우리, NH농협) 및 지방은행(BNK경남은행 등)의 채용 면접관이자 금융 전략 실무자입니다.
    제공된 국내외 5대 경제신문 뉴스(및 첨부된 금융 리포트 PDF)를 바탕으로, 은행권 취업 준비생(AFPK·ADsP 보유, 신용보증재단 대위변제/이행심사 경험 보유)을 위한 일일 리포트를 작성하세요.
    반드시 사실에 기반하여 작성하고, 각 주장에는 위 뉴스 중 어떤 신문사의 기사를 참고했는지 출처를 명시하세요.

    [수집된 오늘의 국내외 5대 경제신문 뉴스]
    {news_text}

    ---
    [필수 출력 양식 - 아래 4가지 목차를 정확히 지켜서 작성할 것]

    ### 1. 오늘의 국내외 핵심 경제/금융 이슈 (3~4줄 요약)
    - 국내 금융시장과 글로벌(미국 월가 등) 동향을 연결하여 핵심만 요약 (출처 신문사 명시)
    - 해당 이슈가 은행의 수익성(예대마진, 비이자이익)에 미치는 긍정적 영향과 반론(부작용/2차 효과)을 나란히 비교

    ### 2. 지원 분야별 맞춤형 해결 방안 및 면접 필승 전략
    - **[기업금융 (RM/여신심사)]**: 금리·환율 변동이나 산업 이슈 속에서 중소기업의 연체율 및 부실(대위변제) 리스크를 줄이기 위한 방안 (지원자의 ADsP 데이터 분석 역량 및 신용보증재단 심사/관리 경험과 연결할 것)
    - **[개인금융 (WM/유니버설 뱅커)]**: 현재 시장 상황에서 창구 내방 고객 및 VIP에게 제안할 수 있는 자산배분(포트폴리오 리밸런싱), 절세, 또는 리스크 헤지 상품 전략 (지원자의 AFPK 전문성과 연결할 것)
    - **[지역인재 (영남/경남권 특화)]**: 위 거시경제 이슈가 창원·경남 등 영남권 주력 산업(기계, 방산, 조선, 자동차부품 등 지역 중소기업 및 소상공인)에 미칠 영향과, BNK경남은행 및 시중은행 영남권 지점 행원으로서 지역 경제를 지원할 수 있는 구체적 영업/상생 아이디어

    ### 3. PDF 심층 리포트 요약 (PDF가 첨부된 경우에만 작성, 없으면 '해당 없음' 표시)
    - 첨부된 보고서의 핵심 통계 수치와 은행권 시사점 정리

    ### 4. 오늘의 필수 금융·경제 시사 용어 사전 (필기 및 면접 대비)
    - 오늘 기사에 등장했거나 관련성이 높은 핵심 경제/금융/산업 용어 3~5개를 선정하여 직관적으로 해설
    - 작성 예시:
      * **리쇼어링(Reshoring)**: 해외에 나가 있는 자국 기업들을 세제 혜택이나 규제 완화를 통해 다시 국내로 불러들이는 정책.
      * (위와 같은 형식으로 3~5개 정리)
    """

    contents = [prompt]

    # 2번 기능 유지: PDF URL이 입력되어 있으면 통째로 읽어서 분석에 포함
    if pdf_url:
        try:
            response = requests.get(pdf_url, timeout=15)
            if response.status_code == 200:
                pdf_part = types.Part.from_bytes(
                    data=response.content,
                    mime_type='application/pdf',
                )
                contents.append(pdf_part)
                contents.append("위 첨부된 PDF 금융 리포트의 핵심 수치와 논리도 1, 2, 3, 4번 목차 분석에 반드시 반영하세요.")
        except Exception as e:
            print(f"PDF 로드 실패(뉴스 분석만 진행합니다): {e}")

    result = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=contents
    )
    return result.text

# 4. 디스코드 전송 함수 (글자수 잘림 방지 처리)
def send_to_discord(message):
    for i in range(0, len(message), 1900):
        chunk = message[i:i+1900]
        requests.post(DISCORD_WEBHOOK_URL, json={"content": chunk})

if __name__ == "__main__":
    news_data = get_econ_news()
    
    # 평소에는 None으로 두면 5대 신문만 분석합니다.
    # 한국은행, 금융연구원 등의 PDF를 같이 분석하고 싶은 날에만 None을 지우고 "https://.../파일.pdf" 주소를 넣으세요.
    target_pdf_url = None 
    
    report = analyze_with_gemini(news_data, target_pdf_url)
    send_to_discord(report)
