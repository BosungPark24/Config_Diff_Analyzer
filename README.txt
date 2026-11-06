ConfigAnalyzer
==============

현재 버전: v0.2
지원 대상: WebLogic, JBoss, Tomcat, Apache, OHS, Nginx

[v0.2 변경사항 - 2026-11-06]

1. 드래그 선택 가시성
   - 선택한 텍스트를 파란색 배경과 흰색 글자로 강조합니다.
   - 추가/삭제/변경 배경색 위에서도 선택 범위를 식별할 수 있습니다.

2. 지원 대상 확장 및 앱 이름 변경
   - 지원 대상 목록에 Apache, OHS, Nginx를 추가했습니다.
   - 앱 이름을 ConfigAnalyzer로 변경했습니다.

3. 버전이 포함된 EXE
   - build_exe.bat은 PyInstaller --onefile --noconsole 옵션으로 빌드합니다.
   - 현재 EXE 이름: dist\ConfigAnalyzer_v0.2.exe
   - 다음 버전 배포 시 was_config_analyzer.py의 APP_VERSION과
     build_exe.bat의 APP_VERSION을 함께 변경하세요.

4. 이전 기능 유지
   - 좌우 파일 비교, 동일 폭 패널, 동기화 세로 스크롤을 제공합니다.
   - 자동 줄 바꿈은 비교 창의 체크박스로 켜고 끌 수 있습니다.
   - .conf 파일은 자동 줄 바꿈이 기본으로 켜집니다.

5. Git 형상관리
   - .gitignore에서 build 및 dist 산출물을 제외합니다.
   - 소스, 빌드 스크립트, README를 Git으로 관리합니다.
   - GitHub 원격 저장소 연결 후 push할 수 있습니다.
