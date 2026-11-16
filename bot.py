import os
import requests
import feedparser
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google import genai
from google.genai import types

# 1. GitHub 비밀 금고(Secrets)에서 환경 변수 불러오기
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")

client = genai.Client(api_key=GEMINI_API_KEY)

# 2. 국내외 5대 경제신문 RSS 수집 (무료)
def get_econ_news():
    rss_sources = {
        "한국경제(경제/금융)": "https://www.hankyung.com/feed/economy",
        "매일경제(헤드라인)": "https://www.mk.co.kr/rss/30000001/",
        "서울경제(마켓/금융)": "https://m.sedaily.com/rss/finance",
        "파이낸셜뉴스(종합)": "https://www.fnnews.com/rss/r20/fn_realnews_all.xml",
        "WSJ/글로벌경제(영문)": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml" 
    }
    
    news_list = []
    for paper_name, url in rss_sources.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]:
                title = entry.title
                summary = entry.get('description', '요약 없음').replace('<p>', '').replace('</p>', '')[:200]
                link = entry.link
                news_list.append(f"[{paper_name}] 제목: {title}\n내용요약: {summary}\n원문링크: {link}")
        except Exception as e:
            print(f"{paper_name} 수집 오류 건너뜀: {e}")
            
    return "\n\n".join(news_list)

# 3. 제미나이 통합 분석 (은행권 면접/실무 맞춤형)
def analyze_with_gemini(news_text, pdf_url=None):
    prompt = f"""
    당신은 시중은행(KB국민, 신한, 하나, 우리, NH농협) 및 지방은행(BNK경남은행 등)의 채용 면접관이자 금융 전략 실무자입니다.
    제공된 국내외 5대 경제신문 뉴스(및 첨부된 금융 리포트 PDF)를 바탕으로, 은행권 취업 준비생(AFPK·ADsP 보유, 신용보증재단 대위변제/이행심사 인턴 경험 보유)을 위한 일일 리포트를 작성하세요.
    반드시 사실에 기반하여 작성하고, 각 주장에는 출처 신문사를 명시하세요.

    [수집된 오늘의 뉴스]
    {news_text}

    [필수 출력 목차]
    ### 1. 오늘의 핵심 경제/금융 이슈 요약 (국내외 시장 연결)
    ### 2. 직무별 맞춤형 해결 방안
       - 기업금융 (여신심사/RM): 중소기업 연체율 및 부실 리스크 관리 방안 (ADsP 및 보증재단 인턴 경험 연계)
       - 개인금융 (WM): VIP 자산배분 및 리밸런싱 전략 (AFPK 지식 연계)
       - 지역인재: 창원/경남권 등 영남권 주력 산업과 연계한 지역 경제 상생 아이디어
    ### 3. PDF 심층 리포트 요약 (첨부된 경우에만 작성)
    ### 4. 오늘의 필수 금융·경제 시사 용어 사전 (3~5개 직관적 해설)
    """

    contents = [prompt]

    if pdf_url:
        try:
            response = requests.get(pdf_url, timeout=15)
            if response.status_code == 200:
                pdf_part = types.Part.from_bytes(data=response.content, mime_type='application/pdf')
                contents.append(pdf_part)
                contents.append("위 첨부된 PDF 금융 리포트의 핵심 수치와 논리도 분석에 반드시 반영하세요.")
        except Exception as e:
            print(f"PDF 로드 실패: {e}")

    result = client.models.generate_content(
        model='gemini-3.8-flash',
        contents=contents
    )
    return result.text

# 4. Gmail 자동 발송 함수
def send_email(report):
    msg = MIMEMultipart()
    msg['From'] = GMAIL_ADDRESS
    msg['To'] = GMAIL_ADDRESS # 나에게 보내기
    msg['Subject'] = "[일일 리포트] 오늘의 은행 실무 맞춤형 경제/금융 분석"

    # 이메일 본문에 리포트 내용 추가
    msg.attach(MIMEText(report, 'plain'))

    try:
        # Gmail SMTP 서버 연결
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        # 앱 비밀번호로 로그인
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("✅ Gmail 발송 완료!")
    except Exception as e:
        print(f"❌ Gmail 발송 실패: {e}")

if __name__ == "__main__":
    # 1. 뉴스 스크랩
    news_data = get_econ_news()
    
    # 2. PDF 심층 분석이 필요한 경우 주소 입력 (평소엔 None)
    target_pdf_url = None 
    
    # 3. 제미나이 리포트 생성
    report = analyze_with_gemini(news_data, target_pdf_url)
    
    # 4. 내 메일함으로 전송
    send_email(report)
