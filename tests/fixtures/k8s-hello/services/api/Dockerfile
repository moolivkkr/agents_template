FROM golang:1.27-alpine AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY *.go ./
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/app .

FROM gcr.io/distroless/static:nonroot
ARG GIT_SHA=unknown
ENV GIT_SHA=$GIT_SHA
COPY --from=build /out/app /app
USER 65532:65532   # numeric: kubelet can only enforce runAsNonRoot on a numeric user
ENTRYPOINT ["/app"]
