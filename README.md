# ConfigAnalyzer

WebLogic, JBoss, Tomcat, Apache HTTP Server, Oracle HTTP Server (OHS), Nginx 등 주요 미들웨어 설정 파일을 순정(Pure) 기준 설정과 비교하는 Windows GUI 도구입니다.

## 다운로드

Windows 64비트용 단독 실행 파일을 내려받아 실행하세요. Python이나 별도 라이브러리를 설치할 필요가 없습니다.

[ConfigAnalyzer v0.2 다운로드](https://github.com/BosungPark24/Config_Diff_Analyzer/raw/main/downloads/ConfigAnalyzer_v0.2.exe)

## 주요 기능

- WebLogic, JBoss, Tomcat, Apache, OHS, Nginx 지원
- 사용자가 버전을 추가하고 순정 설정 파일을 등록·관리
- Baseline 파일은 `baselines/<제품>/<버전>/<파일명>`에 복사하고 메타데이터를 `baselines/metadata.json`으로 저장
- Pure Baseline과 Target Comparison을 좌우로 나란히 표시
- 추가·변경·삭제 줄을 색으로 표시하고 세로 스크롤 동기화
- 드래그 선택 영역을 파란 배경과 흰 글자로 표시해 diff 색상 위에서도 가시성 확보
- `.conf` 파일은 자동 줄 바꿈을 기본 적용하며, 비교 창에서 줄 바꿈을 켜거나 끌 수 있음
- XML 구조 비교, `.properties` 및 `.conf` 키·값 비교
- 비교 결과 CSV 내보내기
- 버전이 포함된 단독 EXE: `ConfigAnalyzer_v0.2.exe`

## 사용 방법

1. 위 다운로드 링크에서 EXE를 내려받아 실행합니다.
2. 왼쪽에서 제품 종류를 선택하고 **버전 추가**를 눌러 버전을 등록합니다.
3. **Pure 파일 등록**을 눌러 순정 설정 파일을 추가합니다.
4. Pure 파일을 선택하고 오른쪽에서 대상 설정 파일을 지정한 뒤 **Compare**를 실행합니다.
5. 초록색은 추가, 노란색은 변경, 빨간색은 삭제 항목입니다. 드래그한 선택 범위는 파란색으로 보입니다.

Baseline 파일은 EXE가 있는 위치의 `baselines` 폴더에 저장됩니다. 해당 폴더에 쓰기 권한이 있는 위치에서 실행하세요.

## 지원 파일

- XML: `.xml`
- Properties 및 일반 설정: `.properties`, `.conf`

## 소스에서 빌드

Python 3.10 이상과 Tkinter가 설치된 Windows 환경에서 `build_exe.bat`를 실행합니다.

```powershell
python -m pip install pyinstaller
.\build_exe.bat
```

결과 파일은 `dist/ConfigAnalyzer_v<버전>.exe`에 생성됩니다. 버전 변경 시 소스의 `APP_VERSION`, 빌드 스크립트의 `APP_VERSION`, EXE 파일명을 함께 갱신하세요.

## 변경 이력

### v0.2

- 앱 이름 및 EXE 이름을 ConfigAnalyzer와 버전 형식으로 변경
- Apache, OHS, Nginx 지원 추가
- 드래그 선택 가시성을 파란색 배경과 흰 글자로 개선
- 좌우 비교 창의 동기화 스크롤, 크기 정렬, 자동 줄 바꿈 제공

### v0.1

- WAS 버전 및 Pure Baseline 파일 관리
- XML, properties, conf 비교
- 전체 파일 좌우 비교, 변경 색상 표시, CSV 내보내기
- 단독 실행 EXE 빌드 구성
