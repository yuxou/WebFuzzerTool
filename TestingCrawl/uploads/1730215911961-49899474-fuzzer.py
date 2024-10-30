# fuzzer.py

import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from collections import deque
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import logging
from datetime import datetime
import asyncio
import aiohttp
import urllib.robotparser
import re

# PDF 리포트 모듈 임포트 (존재한다고 가정)
from report import generate_pdf_report

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("fuzzer.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 정적 크롤러 클래스 정의
class StaticCrawler:
    def __init__(self, base_url, robot_parser=None):
        self.base_url = base_url
        self.robot_parser = robot_parser
        self.visited = set()
        self.to_visit = deque([base_url])
        self.urls = set()

    def is_valid_url(self, url):
        parsed = urlparse(url)
        if parsed.netloc != urlparse(self.base_url).netloc:
            return False
        if parsed.scheme not in ['http', 'https']:
            return False
        if self.robot_parser and not self.robot_parser.can_fetch("*", url):
            logger.info(f"robots.txt에 의해 크롤링이 금지된 URL: {url}")
            return False
        return True

    def crawl(self):
        while self.to_visit:
            url = self.to_visit.popleft()
            if url in self.visited:
                continue
            self.visited.add(url)
            try:
                logger.info(f"[StaticCrawler] 방문 중: {url}")
                response = requests.get(url, timeout=10)
                if response.status_code != 200:
                    logger.warning(f"[StaticCrawler] 비정상적인 상태 코드({response.status_code}) - URL: {url}")
                    continue
                soup = BeautifulSoup(response.text, 'html.parser')
                for link in soup.find_all('a', href=True):
                    new_url = urljoin(self.base_url, link['href'])
                    new_url = new_url.rstrip('/')
                    if self.is_valid_url(new_url) and new_url not in self.visited:
                        self.urls.add(new_url)
                        self.to_visit.append(new_url)
            except requests.RequestException as e:
                logger.error(f"[StaticCrawler] 요청 실패 - URL: {url}, 에러: {e}")
                continue
        logger.info(f"[StaticCrawler] 크롤링 완료: {len(self.urls)}개의 URL 수집.")
        return self.urls

# 동적 크롤러 URL 추출 함수
def extract_urls_dynamic(driver, base_url):
    urls = set()
    try:
        links = driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            href = link.get_attribute("href")
            if href and urlparse(href).scheme in ['http', 'https']:
                href = href.rstrip('/')
                parsed_href = urlparse(href)
                if urlparse(base_url).netloc == parsed_href.netloc:
                    urls.add(href)
    except Exception as e:
        logger.error(f"[DynamicCrawler] URL 추출 중 오류 발생: {e}")
    return urls

# 동적 폼 추출 함수
def extract_forms_dynamic(driver, url):
    forms = []
    independent_inputs = []
    try:
        WebDriverWait(driver, 20).until(
            EC.visibility_of_element_located((By.TAG_NAME, "body"))
        )
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')

        # 폼 추출
        for form in soup.find_all('form'):
            form_details = {}
            action = form.get('action')
            method = form.get('method', 'get').lower()
            inputs = []

            input_tags = form.find_all(['input', 'textarea', 'select', 'button'])
            for input_tag in input_tags:
                tag_name = input_tag.name
                input_type = input_tag.get('type', tag_name)
                input_name = input_tag.get('name')
                if input_name:  # 이름이 있는 필드만 추가
                    inputs.append({'tag': tag_name, 'type': input_type, 'name': input_name})

            form_details['action'] = urljoin(url, action) if action else url
            form_details['method'] = method
            form_details['inputs'] = inputs
            forms.append(form_details)

        # 독립된 입력 필드 추출
        all_input_tags = soup.find_all(['input', 'textarea', 'select', 'button'])
        for input_tag in all_input_tags:
            if not input_tag.find_parent('form'):
                tag_name = input_tag.name
                input_type = input_tag.get('type', tag_name)
                input_name = input_tag.get('name')
                if input_name:  # 이름이 있는 필드만 추가
                    independent_inputs.append({'tag': tag_name, 'type': input_type, 'name': input_name})

        # iframe 내 폼 추출
        frames = driver.find_elements(By.TAG_NAME, "iframe")
        for frame in frames:
            try:
                driver.switch_to.frame(frame)
                frame_forms, frame_independent_inputs = extract_forms_dynamic(driver, url)
                forms.extend(frame_forms)
                independent_inputs.extend(frame_independent_inputs)
                driver.switch_to.default_content()
            except Exception as e:
                logger.error(f"[DynamicCrawler] iframe 내 폼 추출 중 오류 발생: {e}")
                driver.switch_to.default_content()

    except Exception as e:
        logger.error(f"[DynamicCrawler] 폼 추출 중 오류 발생 - URL: {url}, 에러: {e}")

    # 디버깅을 위해 추출된 폼 로그 추가
    if not forms:
        logger.info(f"[DynamicCrawler] URL: {url}에 폼이 존재하지 않습니다.")
    else:
        for form in forms:
            logger.info(f"[DynamicCrawler] 폼 발견 - 액션: {form['action']}, 메소드: {form['method'].upper()}, 입력 필드: {form['inputs']}")

    return forms, independent_inputs

# 동적 크롤링 함수
def crawl_dynamic(driver, base_url, max_depth, visited_urls, extraction_results, robot_parser=None):
    queue = deque()
    base_parsed = urlparse(base_url)
    base_url_clean = base_parsed.scheme + "://" + base_parsed.netloc + base_parsed.path
    queue.append((base_url_clean, 0))  # 프래그먼트 없이 기본 URL로 시작

    while queue:
        current_url, depth = queue.popleft()

        # URL 프래그먼트 제거
        current_url = urlparse(current_url)._replace(fragment="").geturl()

        if current_url in visited_urls:
            continue

        if depth > max_depth:
            logger.info(f"[DynamicCrawler] 최대 깊이({max_depth}) 도달 - URL: {current_url}, 스킵.")
            continue

        logger.info(f"[DynamicCrawler] 방문 중: {current_url}, 깊이: {depth}")
        try:
            driver.get(current_url)

            # JavaScript가 페이지를 완전히 렌더링할 시간을 주기 위해 대기
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            current_after_redirect = driver.current_url
            parsed_current = urlparse(current_after_redirect)

            # robots.txt에 의해 크롤링이 금지된 URL인지 확인
            if robot_parser and not robot_parser.can_fetch("*", current_after_redirect):
                logger.info(f"robots.txt에 의해 크롤링이 금지된 URL: {current_after_redirect}")
                visited_urls.add(current_after_redirect)
                continue

            visited_urls.add(current_after_redirect)

            forms, independent_inputs = extract_forms_dynamic(driver, current_after_redirect)
            logger.info(f"[DynamicCrawler] 발견된 폼: {len(forms)}개, 독립 입력 필드: {len(independent_inputs)}개 - URL: {current_after_redirect}")

            result = {
                'url': current_after_redirect,
                'forms': forms,
                'independent_inputs': independent_inputs,
                'fuzzing_results': []
            }
            extraction_results.append(result)

            # 새로운 URL 추출 및 큐에 추가
            new_urls = extract_urls_dynamic(driver, base_url)
            for url in new_urls:
                url_clean = urlparse(url)._replace(fragment="").geturl()
                if url_clean not in visited_urls:
                    if robot_parser and not robot_parser.can_fetch("*", url_clean):
                        logger.info(f"robots.txt에 의해 크롤링이 금지된 URL: {url_clean}")
                        continue
                    queue.append((url_clean, depth + 1))

        except Exception as e:
            logger.error(f"[DynamicCrawler] 방문 중 오류 발생 - URL: {current_url}, 에러: {e}")

# 퍼징 클래스 정의
class AsyncFuzzer:
    def __init__(self, forms, payloads, concurrency=10):
        self.forms = forms
        self.payloads = payloads
        self.concurrency = concurrency
        self.vulnerabilities = []
        self.attempts = []

    async def fuzz_form(self, session, form, payload):
        data = {}
        injectable_types = ['text', 'search', 'email', 'url', 'tel', 'password']
        for input_field in form['inputs']:
            input_type = input_field['type'].lower()
            input_name = input_field['name']
            if input_name:
                if input_type in injectable_types:
                    data[input_name] = payload
                else:
                    data[input_name] = 'test'
        try:
            if form['method'] == 'post':
                logger.debug(f"POST 요청 발송 - URL: {form['action']}, 데이터: {data}")
                async with session.post(form['action'], data=data) as response:
                    text = await response.text()
                    logger.debug(f"응답 수신 - 상태 코드: {response.status}")
                    self.analyze_response(text, payload, form, response.status)
            else:
                logger.debug(f"GET 요청 발송 - URL: {form['action']}, 파라미터: {data}")
                async with session.get(form['action'], params=data) as response:
                    text = await response.text()
                    logger.debug(f"응답 수신 - 상태 코드: {response.status}")
                    self.analyze_response(text, payload, form, response.status)
        except Exception as e:
            logger.error(f"[AsyncFuzzer] 요청 실패 - 폼: {form['action']}, 페이로드: '{payload}', 에러: {e}")
            self.attempts.append({
                'form_action': form['action'],
                'payload': payload,
                'result': f"요청 실패: {e}"
            })

    def analyze_response(self, text, payload, form, status):
        vulnerability_detected = False
        result = "취약점 없음"

        # SQL Injection 에러 패턴
        sql_errors = [
            r'syntax error',
            r'unclosed quotation mark',
            r'unterminated string constant',
            r'you have an error in your sql syntax',
            r'warning: mysql',
            r'sqlite error',
            r'pg_query\(\):',
            r'pdoexception'
            # 필요한 경우 추가 패턴 작성
        ]

        for error_pattern in sql_errors:
            if re.search(error_pattern, text, re.IGNORECASE):
                self.vulnerabilities.append({
                    'type': 'SQL Injection',
                    'payload': payload,
                    'form': form['action'],
                    'response_code': status
                })
                vulnerability_detected = True
                result = "SQL Injection 취약점 발견"
                break

        if not vulnerability_detected and payload in text:
            self.vulnerabilities.append({
                'type': 'Reflected XSS',
                'payload': payload,
                'form': form['action'],
                'response_code': status
            })
            vulnerability_detected = True
            result = "반사형 XSS 취약점 발견"

        if vulnerability_detected:
            logger.info(f"[AsyncFuzzer] 취약점 발견 - 폼: {form['action']}, 페이로드: '{payload}', 결과: {result}")

        self.attempts.append({
            'form_action': form['action'],
            'payload': payload,
            'result': result
        })

    async def run(self):
        connector = aiohttp.TCPConnector(limit=self.concurrency, ssl=False)
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            tasks = []
            for form in self.forms:
                for payload in self.payloads:
                    tasks.append(self.fuzz_form(session, form, payload))
            await asyncio.gather(*tasks)
        logger.info(f"[AsyncFuzzer] 퍼징 완료. 취약점 발견: {len(self.vulnerabilities)}개")

# 메인 함수 정의
def main():
    base_url = input("크롤링할 기본 URL을 입력하세요: ").strip()
    try:
        max_depth = int(input("최대 크롤링 깊이를 입력하세요: ").strip())
    except ValueError:
        logger.error("최대 크롤링 깊이는 정수여야 합니다.")
        return

    # robots.txt 체크
    robots_url = urljoin(base_url, '/robots.txt')  # 올바른 robots.txt URL 생성
    rp = urllib.robotparser.RobotFileParser()
    try:
        response = requests.get(robots_url, timeout=10)
        if response.status_code == 200:
            rp.parse(response.text.splitlines())
            logger.info("robots.txt가 발견되었습니다. 크롤링 규칙을 따릅니다.")
        else:
            logger.info("robots.txt가 존재하지 않습니다. 크롤링 규칙을 제한하지 않습니다.")
            rp = None
    except requests.RequestException as e:
        logger.error(f"robots.txt 접근 실패 - 에러: {e}")
        rp = None

    # 정적 크롤러 초기화 및 실행
    static_crawler = StaticCrawler(base_url, rp)
    static_crawled_urls = static_crawler.crawl()

    # Selenium WebDriver 초기화 (헤드리스 모드 비활성화)
    chrome_options = Options()
    # chrome_options.add_argument("--headless")  # 헤드리스 모드 비활성화: 주석 처리
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    try:
        driver = webdriver.Chrome(options=chrome_options)
    except Exception as e:
        logger.error(f"Selenium WebDriver 초기화 실패: {e}")
        return

    visited_urls_dynamic = set()
    extraction_results_dynamic = []

    try:
        crawl_dynamic(driver, base_url, max_depth, visited_urls_dynamic, extraction_results_dynamic, rp)
    finally:
        driver.quit()

    # 정적 및 동적 크롤러에서 수집한 URL 결합
    combined_urls = static_crawled_urls.union(visited_urls_dynamic)

    # 동적 크롤러 결과에서 폼 추출
    forms = []
    for result in extraction_results_dynamic:
        forms.extend(result['forms'])
        # 독립된 입력 필드가 있는 경우 별도의 폼으로 추가
        for input_field in result['independent_inputs']:
            if input_field['name']:
                forms.append({
                    'action': result['url'],
                    'method': 'get',
                    'inputs': [input_field]
                })

    # 입력 필드가 없는 폼 제거
    forms = [form for form in forms if form['inputs']]

    if not forms:
        logger.info("[Main] 퍼징할 폼이 발견되지 않았습니다.")
        vulnerabilities = []
        attempts = []
    else:
        # 퍼징 페이로드 정의
        sql_injection_payloads = [
            "' OR '1'='1' --",
            "' OR '1'='1' /*",
            "admin' --",
            "' OR '1'='1' #",
        ]

        xss_payloads = [
            "<script>alert('Test')</script>",
            "<img src=x onerror=alert('Test')>",
            "<svg/onload=alert('Test')>",
            "<body onload=alert('Test')>",
        ]

        payloads = sql_injection_payloads + xss_payloads
        fuzzer = AsyncFuzzer(forms, payloads, concurrency=10)
        asyncio.run(fuzzer.run())
        vulnerabilities = fuzzer.vulnerabilities
        attempts = fuzzer.attempts  # 퍼징 시도 내역 가져오기

    # PDF 리포트 생성 (선택 사항)
    generate_pdf_report(
        crawled_urls=combined_urls,
        extraction_results=extraction_results_dynamic,
        vulnerabilities=vulnerabilities if vulnerabilities else [],
        attempts=attempts if attempts else [],
        output_path='fuzzer_report.pdf'
    )

    logger.info("[Main] 웹 퍼징이 완료되었습니다.")

if __name__ == "__main__":
    main()