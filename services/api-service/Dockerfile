FROM golang:1.23-alpine AS build

WORKDIR /src
RUN apk add --no-cache ca-certificates

COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /bin/api-service ./cmd/api

FROM alpine:3.20

RUN apk add --no-cache ca-certificates
COPY --from=build /bin/api-service /bin/api-service

EXPOSE 8080
ENTRYPOINT ["/bin/api-service"]

