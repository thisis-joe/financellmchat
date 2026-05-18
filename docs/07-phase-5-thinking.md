# 07. 5차 배포 사고 흐름

5차의 목표는 "내 컴퓨터에서는 되는데, 다른 사람이 어떻게 접속하지?"라는 문제를 정리하는 것이었다.  
이 프로젝트는 Spring Boot, Python RAG, MySQL, 로컬 LLM 실행이 함께 필요하다. 그래서 단순히 Vercel 하나에 전부 올리는 방식은 맞지 않았다.

먼저 프론트와 백엔드의 성격을 나누어 보았다. 프론트는 `index.html`, `style.css`, `app.js` 세 파일뿐이다. 빌드 과정도 없고 서버 상태도 없다. 이런 정적 파일은 Vercel 무료 배포에 잘 맞는다. 반대로 백엔드는 Spring Boot가 떠 있어야 하고, Spring은 Python RAG를 호출해야 하며, Python은 MySQL과 PDF chunk를 읽고 Gemma 모델을 실행한다. 이 묶음은 Vercel의 정적 배포 대상이 아니다.

그래서 배포 방향은 `Vercel 정적 프론트 + Cloudflare Tunnel API`로 정했다. 사용자는 Vercel에 접속하지만, 질문을 보내는 `/api/*` 요청은 `vercel.json` rewrite를 통해 `https://api.bnkaichat.xyz`로 넘어간다. 이 API 도메인은 Cloudflare Tunnel에 연결되어 있고, Tunnel은 개인 Mac의 `localhost:8080` Spring Boot로 요청을 전달한다.

이 판단의 장점은 명확하다. 공유기 포트포워딩이나 집 IP 공개 없이 로컬 Spring API를 외부에서 부를 수 있다. 또한 프론트와 API가 서로 다른 위치에 있어도 브라우저 코드는 계속 `/api/ask`만 호출하면 된다. 프론트 입장에서는 개발 중에도, Vercel 배포 후에도 같은 경로를 쓰는 셈이다.

이번 배포에서 직접 관련된 파일은 `src/main/resources/static/vercel.json`이다. 이 파일은 Vercel이 `/api/:path*` 요청을 `https://api.bnkaichat.xyz/api/:path*`로 넘기게 한다. 코드를 복잡하게 바꾸지 않고 배포 플랫폼의 rewrite 기능을 사용한 이유는 프론트 JavaScript에 운영용 API 주소를 하드코딩하지 않기 위해서다.

배포 중에는 Vercel 기본 도메인에서 404가 뜨는 문제도 있었다. 원인은 Vercel이 repo 루트를 프로젝트 루트로 보고 있었는데, 실제 정적 파일은 `src/main/resources/static` 아래에 있었기 때문이다. 이 문제는 루트 `vercel.json`에 `outputDirectory: "src/main/resources/static"`을 명시해서 해결했다. 만약 Vercel Root Directory를 정적 파일 폴더로 직접 지정한다면, 그 폴더 안의 `vercel.json`만으로 rewrite를 처리할 수 있다.

이후 `https://financellmchat.vercel.app`에서 정적 화면이 200으로 열리는지 확인했고, 같은 주소에 대표 질문 10개 스크립트를 실행해 `/api/*` rewrite가 Cloudflare Tunnel API까지 이어지는지도 확인했다. 여기서 중요한 점은 "화면이 뜬다"와 "질문이 답변까지 간다"를 따로 확인해야 한다는 것이다. Vercel은 정적 파일을 잘 보여도 API rewrite나 Tunnel이 끊기면 챗봇은 동작하지 않는다.

Cloudflare에서 기다리라는 상태도 정리했다. 이 상태는 대개 가비아에서 Cloudflare nameserver로 바꾼 뒤 전파를 기다리는 단계다. 이때는 Spring 코드나 Vercel 설정을 계속 바꾸기보다, 가비아에 입력한 nameserver가 정확한지 확인하고 Cloudflare가 도메인을 활성화할 때까지 기다리는 편이 맞다. 활성화 전에는 `api.bnkaichat.xyz`가 제대로 동작하지 않을 수 있다.

커스텀 도메인도 역할을 나누었다. `bnkaichat.xyz`나 `www.bnkaichat.xyz`는 사용자가 접속하는 Vercel 프론트 도메인으로 쓰고, `api.bnkaichat.xyz`는 Cloudflare Tunnel이 로컬 Spring Boot로 보내는 API 도메인으로 유지한다. 두 도메인을 섞으면 Vercel과 Tunnel이 서로 다른 역할을 하면서도 같은 이름을 차지하려고 해 설정이 꼬이기 쉽다.

배포의 위험도도 함께 보았다. 개인 Mac이 꺼지거나 절전 상태가 되면 API도 멈춘다. Spring은 떠 있어도 Python RAG가 꺼져 있으면 모델 기반 답변은 실패할 수 있다. Python이 떠 있어도 MySQL이 꺼져 있으면 검색할 문서를 읽지 못한다. 그래서 배포 문서에는 Vercel 설정뿐 아니라 MySQL, Spring, Python, Cloudflare Tunnel을 각각 확인하는 명령을 같이 남겼다.

5차의 결론은 "배포도 아키텍처의 일부"라는 것이다. 단순히 화면을 인터넷에 올리는 문제가 아니라, 정적 프론트, API, 로컬 모델, DB, 원본 PDF 다운로드가 어떤 경로로 연결되는지 설명할 수 있어야 한다. 지금 방식은 운영용 정답이라기보다 학습과 시연에 맞춘 가장 단순한 배포 경로다. 나중에 실제 서비스로 확장한다면 Spring API, Python RAG, MySQL, PDF 저장소를 클라우드 환경으로 옮기고, 각 서비스의 장애와 비용을 따로 관리해야 한다.

## 다음 과제

외부 배포가 안정되면 다음 과제는 운영 확인이다. 최소한 `/health`, `/api/ask`, PDF 다운로드를 주기적으로 확인하는 스크립트를 만들고, 실패 시 로그를 확인할 수 있어야 한다. 그 다음에는 Docker 없이도 재시작 절차를 줄이기 위해 `launchd`나 서비스 등록을 정리하는 것이 좋다.

장기적으로는 로컬 Mac 의존도를 줄이는 방향도 검토할 수 있다. 예를 들어 MySQL은 관리형 DB로 옮기고, Spring API는 일반 서버나 PaaS에 올리며, Python RAG는 GPU가 필요한 경우 별도 inference 서버로 분리하는 방식이다. 다만 지금은 Spring MVC와 RAG 흐름을 이해하는 것이 우선이므로, Vercel과 Cloudflare Tunnel 조합이 가장 작고 설명하기 쉬운 선택이다.

## 용어 메모

- 정적 프론트: 서버에서 매번 생성하지 않고 HTML, CSS, JS 파일 그대로 배포되는 화면이다.
- Vercel: 정적 사이트와 프론트엔드 프로젝트를 배포하는 플랫폼이다.
- Cloudflare Tunnel: 외부 요청을 로컬 서버로 전달하는 보안 터널이다.
- DNS 전파: 도메인 설정 변경이 인터넷의 여러 DNS 서버에 퍼지는 과정이다.
- nameserver: 도메인의 DNS 설정을 어느 서비스가 관리하는지 알려주는 서버다.
- rewrite: 사용자가 요청한 URL 경로를 다른 서버 주소로 전달하는 규칙이다.
- Root Directory: Vercel이 프로젝트 루트로 인식하는 폴더다.
- Output Directory: Vercel이 실제 정적 파일을 찾아 서빙하는 결과 폴더다.
- 기본 도메인: Vercel이 배포마다 제공하는 `*.vercel.app` 주소다. 커스텀 도메인 연결 전 검증에 유용하다.
- 커스텀 도메인: 사용자가 구매한 도메인이다. 이 프로젝트에서는 `bnkaichat.xyz`를 프론트 접속 주소로 쓰는 방향이다.
- 포트포워딩: 공유기에서 외부 요청을 내부 PC의 특정 포트로 넘기는 설정이다.
- 운영 확인: 배포된 서비스가 실제로 살아 있는지 API, 로그, 상태값으로 확인하는 작업이다.
