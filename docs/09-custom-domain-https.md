# 09. 커스텀 도메인과 HTTPS 적용

이 문서는 `https://financellmchat.vercel.app`은 접속되지만 `https://bnkaichat.xyz`가 접속되지 않을 때 확인하고 적용하는 절차를 정리한다.  
현재 목표는 `bnkaichat.xyz`를 Vercel 정적 프론트 도메인으로 쓰고, `api.bnkaichat.xyz`는 Cloudflare Tunnel API 도메인으로 분리하는 것이다.

## 현재 진단

확인한 상태는 다음과 같다.

```bash
curl -I https://financellmchat.vercel.app/
# HTTP/2 200

curl --resolve bnkaichat.xyz:443:104.21.7.86 https://bnkaichat.xyz
# error code: 1016

curl -I https://api.bnkaichat.xyz/index.html
# HTTP/2 200
```

의미는 명확하다. Vercel 기본 도메인은 정상이고, Cloudflare Tunnel API도 정상이다. 문제는 `bnkaichat.xyz` 프론트 도메인이다.

`1016`은 보통 Cloudflare가 원본 서버를 DNS로 찾지 못한다는 뜻이다. 즉, HTTPS 인증서만 아직 안 나온 문제가 아니라 Cloudflare DNS 레코드의 원본 대상이 잘못됐거나, Vercel 커스텀 도메인 연결이 끝나지 않은 상태로 봐야 한다.

## 권장 구조

도메인은 역할을 나눈다.

```text
bnkaichat.xyz
  -> Vercel 정적 프론트

www.bnkaichat.xyz
  -> Vercel 정적 프론트

api.bnkaichat.xyz
  -> Cloudflare Tunnel
  -> 개인 Mac localhost:8080 Spring Boot
```

프론트 도메인과 API 도메인을 섞지 않는다. 특히 `api.bnkaichat.xyz`를 Vercel에 연결하지 않는다.

## Vercel에서 도메인 추가

Vercel 대시보드에서 다음 순서로 진행한다.

1. Vercel 프로젝트 `financellmchat`으로 들어간다.
2. `Settings` > `Domains`로 이동한다.
3. `bnkaichat.xyz`를 추가한다.
4. 필요하면 `www.bnkaichat.xyz`도 추가한다.
5. Vercel이 안내하는 DNS 값을 확인한다.

Vercel 문서 기준 일반적인 값은 다음과 같다. 단, Vercel 화면에 프로젝트별 값이 표시되면 화면에 표시된 값을 우선한다.

```text
apex domain: bnkaichat.xyz
Type: A
Name: @
Value: 76.76.21.21

subdomain: www.bnkaichat.xyz
Type: CNAME
Name: www
Value: cname.vercel-dns-0.com
```

Vercel은 도메인 연결과 DNS 검증이 끝나면 HTTPS 인증서를 자동으로 발급한다. 별도로 로컬에서 인증서 파일을 만들 필요가 없다.

## Cloudflare DNS 설정

Cloudflare의 `bnkaichat.xyz` DNS 화면에서 프론트용 레코드를 다음처럼 맞춘다.

```text
Type: A
Name: @
Content: 76.76.21.21
Proxy status: DNS only
TTL: Auto
```

`www`를 쓸 경우:

```text
Type: CNAME
Name: www
Content: cname.vercel-dns-0.com
Proxy status: DNS only
TTL: Auto
```

중요한 점은 프론트용 `@`, `www` 레코드는 우선 `DNS only`로 둔다는 것이다. Vercel은 Cloudflare 같은 외부 reverse proxy를 앞에 두는 구성을 권장하지 않는다. `DNS only`로 두면 브라우저가 Vercel에 직접 도달하고, Vercel이 HTTPS 인증서를 자동 발급한다.

반대로 `api` 레코드는 Cloudflare Tunnel이 사용하므로 기존 설정을 유지한다.

```text
api.bnkaichat.xyz
  -> Cloudflare Tunnel finance-rag-api
```

## SSL/TLS 설정

프론트용 `bnkaichat.xyz`와 `www.bnkaichat.xyz`를 `DNS only`로 둔다면 Cloudflare SSL/TLS 모드는 프론트 트래픽에 관여하지 않는다. HTTPS 인증서는 Vercel이 자동 발급하고 적용한다.

Cloudflare에서 `api.bnkaichat.xyz`는 프록시/Tunnel을 사용하므로 Cloudflare가 브라우저와의 HTTPS를 처리한다. 현재 시연 구조에서는 `api.bnkaichat.xyz`가 다음 명령에서 200을 반환하는지가 가장 직접적인 확인 기준이다.

```bash
curl -I https://api.bnkaichat.xyz/index.html
```

만약 Vercel 인증서가 계속 발급되지 않으면 Cloudflare DNS에 CAA 레코드가 있는지 확인한다. CAA가 있다면 Vercel이 사용하는 인증기관을 허용해야 한다. 일반적으로 다음 값이 필요할 수 있다.

```text
Type: CAA
Name: @
Flags: 0
Tag: issue
Value: letsencrypt.org
```

## 적용 후 확인

DNS 전파는 몇 분에서 길게는 수 시간이 걸릴 수 있다. 적용 뒤 다음 명령으로 확인한다.

```bash
dig +short bnkaichat.xyz A
dig +short www.bnkaichat.xyz CNAME
```

프론트 도메인을 `DNS only`로 둔 경우 기대값은 다음과 비슷하다.

```text
bnkaichat.xyz A -> 76.76.21.21
www.bnkaichat.xyz CNAME -> cname.vercel-dns-0.com
```

HTTPS 확인:

```bash
curl -I https://bnkaichat.xyz
curl -I https://www.bnkaichat.xyz
```

정상이라면 `HTTP/2 200` 또는 Vercel의 redirect 응답이 나오고, 응답 헤더에 `server: Vercel`이 보인다.

인증서 확인:

```bash
openssl s_client -connect bnkaichat.xyz:443 -servername bnkaichat.xyz </dev/null 2>/dev/null \
  | openssl x509 -noout -subject -issuer -dates
```

대표 질문 확인:

```bash
python3 scripts/check_representative_questions.py \
  --base-url https://bnkaichat.xyz \
  --timeout 90
```

이 스크립트가 성공하면 Vercel 프론트, `/api/*` rewrite, Cloudflare Tunnel API, Spring, Python RAG까지 이어진 것이다.

## 오류별 해석

`Could not resolve host`가 나오면 DNS 전파 전이거나 레코드가 없는 상태다.

`error code: 1016`이 나오면 Cloudflare가 원본 DNS 대상을 찾지 못하는 상태다. 프론트 레코드의 대상 값을 Vercel 안내값으로 고치고, `Proxy status`를 `DNS only`로 바꾼다.

Vercel 404가 나오면 DNS는 Vercel까지 갔지만 Vercel 프로젝트에 해당 도메인이 등록되지 않았을 가능성이 크다. Vercel `Settings > Domains`에 `bnkaichat.xyz`가 있는지 확인한다.

인증서 오류가 나오면 Vercel 도메인 상태가 `Valid Configuration`인지 확인하고, CAA 레코드가 인증서 발급을 막고 있지 않은지 확인한다.

## 용어 메모

- apex domain: `bnkaichat.xyz`처럼 `www` 같은 앞부분이 없는 루트 도메인이다.
- subdomain: `www.bnkaichat.xyz`, `api.bnkaichat.xyz`처럼 앞부분이 붙은 도메인이다.
- DNS only: Cloudflare가 DNS 응답만 하고 HTTP/HTTPS 트래픽은 원본으로 직접 보내는 설정이다.
- Proxied: Cloudflare가 HTTP/HTTPS 트래픽 중간에 들어가 보안, 캐시, TLS 처리를 수행하는 설정이다.
- HTTPS 인증서: 브라우저가 안전한 연결인지 확인할 때 쓰는 인증서다.
- CAA: 어떤 인증기관이 해당 도메인의 인증서를 발급할 수 있는지 제한하는 DNS 레코드다.
- 1016 Origin DNS Error: Cloudflare가 DNS 레코드의 원본 서버 이름을 해석하지 못할 때 나오는 오류다.
- reverse proxy: 사용자 요청을 받아 뒤쪽의 다른 서버로 전달하는 중간 서버다.
