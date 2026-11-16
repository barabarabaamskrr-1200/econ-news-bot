import os
import sys
import re
import requests
import feedparser
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google import genai
from google.genai import types

# 1. 환경 변수 불러오기 및 공백/오타 자동 제거
GEMINI_API_KEY = (os.environ.get("GEMINI_API_KEY") or "").strip()
GMAIL_ADDRESS = (os.environ.get("GMAIL_ADDRESS") or "").strip()
GMAIL_APP_PASSWORD = (os.environ.get("GMAIL_APP_PASSWORD") or "").replace(" ", "").strip()

if not GEMINI_API_KEY or not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
    print("❌ [치명적 오류] GitHub Secrets 설정이 누락되었습니다.")
    sys.exit(1)

client = genai.Client(api_key=GEMINI_API_KEY)

# 2. 국내 5대 + 국외 2대 경제신문 RSS 수집 (최신 작동 주소 반영)
def get_econ_news():
    rss_sources = {
        "한국경제": "https://www.hankyung.com/feed/finance", # 최신 금융/마켓 피드
        "매일경제": "https://www.mk.co.kr/rss/30000001/",
        "서울경제": "https://www.sedaily.com/RSS/Economy",
        "머니투데이": "https://rss.mt.co.kr/mt_news.xml",
        "헤럴드경제": "https://biz.heraldcorp.com/rss/010000000000.xml", # 최신 헤럴드경제 피드
        "WSJ(월스트리트저널)": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
        "CNBC(글로벌마켓)": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    
    news_list = []
    for paper_name, url in rss_sources.items():
        try:
            response = requests.get(url, headers=headers, timeout=15)
            feed = feedparser.parse(response.content)
            
            count = 0
            for entry in feed.entries[:3]:
                title = entry.get('title', '제목 없음').strip()
                raw_summary = entry.get('description', entry.get('summary', '요약 없음'))
                clean_summary = re.sub('<[^<]+?>', '', raw_summary).strip()[:200]
                link = entry.get('link', '')
                
                news_list.append(f"[{paper_name}] 제목: {title}\n요약: {clean_summary}\n링크: {link}")
                count += 1
            print(f"✅ {paper_name}: {count}개 기사 수집 성공")
        except Exception as e:
            print(f"⚠️ {paper_name} 수집 건너뜀: {e}")
            
    if not news_list:
        print("❌ 수집된 뉴스가 하나도 없습니다.")
        sys.exit(1)
        
    return "\n\n".join(news_list)

# 3. 제미나이 통합 분석 (은행권 기업금융/WM/영남권 지역인재 맞춤형)
def analyze_with_gemini(news_text, pdf_url=None):
    prompt = f"""
    당신은 시중은행(KB국민, 신한, 하나, 우리, NH농협) 및 지방은행(BNK경남은행 등)의 채용 면접관이자 금융 전략 실무자입니다.
    제공된 국내 5대 및 국외 2대 경제신문 뉴스를 바탕으로, 은행권 취업 준비생(AFPK·ADsP 보유, 신용보증재단 대위변제/이행심사 경험 보유)을 위한 일일 리포트를 작성하세요.
    반드시 제공된 사실에 기반하여 작성하고, 각 주장에는 어떤 신문사의 기사를 참고했는지 출처를 명시하세요.

    [수집된 오늘의 국내외 7대 경제신문 뉴스]
    {news_text}

    ---
    [필수 출력 양식 - 아래 4가지 목차를 정확히 지켜서 작성할 것]

    ### 1. 오늘의 국내외 핵심 경제/금융 이슈 (국내 5대지 & 월가 WSJ/CNBC 동향 연결 요약)
    - 핵심 흐름 요약 (출처 신문사 명시)
    - 해당 이슈가 은행 수익성(예대마진, 비이자이익)과 건전성에 미치는 긍정적 영향과 반론(부작용/2차 효과) 비교

    ### 2. 지원 분야별 맞춤형 해결 방안 및 면접 필승 전략
    - [기업금융 (RM/여신심사)]: 금리·환율·산업 이슈 속에서 중소기업 연체율 및 부실(대위변제) 리스크 관리 방안 (ADsP 데이터 분석 역량 및 신용보증재단 심사/관리 경험 연계)
    - [개인금융 (WM/유니버설 뱅커)]: 현재 시장 상황에서 창구 VIP 및 일반 고객에게 제안할 자산배분(포트폴리오 리밸런싱), 절세, 리스크 헤지 전략 (AFPK 전문성 연계)
    - [지역인재 (영남/경남권 특화)]: 위 거시경제 이슈가 창원·경남 등 영남권 주력 산업(기계, 방산, 조선, 자동차부품 등)에 미칠 영향과, BNK경남은행 및 시중은행 영남권 지점 행원으로서 지역 중소기업·소상공인을 지원할 구체적 영업/상생 방안

    ### 3. PDF 심층 리포트 요약 (첨부된 경우에만 작성, 없으면 '해당 없음' 표시)

    ### 4. 오늘의 필수 금융·경제 시사 용어 사전 (필기 및 면접 대비)
    - 오늘 기사에 등장한 핵심 경제/금융 용어 4~5개를 선정하여 '단어: 직관적 해설' 형태로 정리
    """

    contents = [prompt]

    if pdf_url:
        try:
            response = requests.get(pdf_url, timeout=15)
            if response.status_code == 200:
                pdf_part = types.Part.from_bytes(data=response.content, mime_type='application/pdf')
                contents.append(pdf_part)
                contents.append("위 첨부된 PDF 금융 리포트의 핵심 수치도 분석에 반드시 반영하세요.")
        except Exception as e:
            print(f"⚠️ PDF 로드 실패(뉴스 분석만 진행): {e}")

    result = client.models.generate_content(
        model='gemini-3.8-flash',
        contents=contents
    )
    return result.text

# 4. Gmail 발송 함수 (GitHub 서버 방화벽 통과용 587 TLS 포트 사용)
def send_email(report):
    msg = MIMEMultipart()
    msg['From'] = GMAIL_ADDRESS
    msg['To'] = GMAIL_ADDRESS
    msg['Subject'] = "[일일 경제브리핑] 국내외 7대 경제지 & 은행 직무 맞춤형 분석 리포트"

    msg.attach(MIMEText(report, 'plain', 'utf-8'))

    try:
        # 465 포트 차단 우회를 위해 587 포트(STARTTLS) + 30초 타임아웃 적용
        server = smtplib.SMTP('smtp.gmail.com', 587, timeout=30)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("✅ Gmail 발송 성공! 지금 메일함(받은편지함/스팸함)을 확인하세요.")
    except Exception as e:
        print(f"❌ Gmail 발송 실패 상세 원인: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("1. 국내외 7대 경제신문 뉴스 수집 시작...")
    news_data = get_econ_news()
    
    target_pdf_url = None 
    
    print("2. 제미나이 직무 맞춤형 분석 시작...")
    report = analyze_with_gemini(news_data, target_pdf_url)
    
    print("3. Gmail 전송 시작...")
    send_email(report)
