# Документация для фронтенда

Минимальный OpenAPI-дескриптор публичных endpoint'ов API Gateway. Все запросы требуют HTTPS и заголовок `Authorization` (кроме health).

```yaml
openapi: 3.0.3
info:
  title: Orion Public API
  version: 1.0.0
servers:
  - url: https://api.orion.internal
paths:
  /api/v1/health:
    get:
      summary: Healthcheck
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                type: object
                properties:
                  status:
                    type: string
                    example: ok
  /api/v1/auth/me:
    get:
      summary: Профиль текущего пользователя
      security:
        - bearerAuth: []
      responses:
        '200':
          description: Профиль
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/UserProfile'
  /api/v1/assistant/query:
    post:
      summary: RAG ассистент
      security:
        - bearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AssistantQueryRequest'
      responses:
        '200':
          description: Ответ ассистента
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AssistantResponse'
        '400':
          description: Ошибка валидации или блокировка safety
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
  /api/v1/documents:
    get:
      summary: Список документов
      security:
        - bearerAuth: []
      parameters:
        - in: query
          name: status
          schema:
            type: string
        - in: query
          name: product
          schema:
            type: string
        - in: query
          name: tag
          schema:
            type: string
        - in: query
          name: search
          schema:
            type: string
      responses:
        '200':
          description: Список
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/DocumentItem'
  /api/v1/documents/{doc_id}:
    get:
      summary: Детали документа
      security:
        - bearerAuth: []
      parameters:
        - in: path
          name: doc_id
          required: true
          schema:
            type: string
      responses:
        '200':
          description: Карточка
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/DocumentDetail'
  /api/v1/documents/upload:
    post:
      summary: Загрузка документа
      security:
        - bearerAuth: []
      requestBody:
        required: true
        content:
          multipart/form-data:
            schema:
              type: object
              properties:
                file:
                  type: string
                  format: binary
                product:
                  type: string
                version:
                  type: string
                tags:
                  type: string
              required:
                - file
      responses:
        '202':
          description: Документ принят
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/DocumentUploadResponse'
components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
  schemas:
    UserProfile:
      type: object
      properties:
        user_id:
          type: string
        username:
          type: string
        display_name:
          type: string
          nullable: true
        roles:
          type: array
          items:
            type: string
        tenant_id:
          type: string
    AssistantQueryRequest:
      type: object
      required:
        - query
      properties:
        query:
          type: string
        language:
          type: string
          default: ru
        context:
          type: object
          properties:
            channel:
              type: string
            ui_session_id:
              type: string
            conversation_id:
              type: string
    AssistantResponse:
      type: object
      properties:
        answer:
          type: string
        sources:
          type: array
          items:
            $ref: '#/components/schemas/AssistantSource'
        meta:
          $ref: '#/components/schemas/AssistantResponseMeta'
    AssistantSource:
      type: object
      properties:
        doc_id:
          type: string
        doc_title:
          type: string
          nullable: true
        section_id:
          type: string
          nullable: true
        section_title:
          type: string
          nullable: true
        page_start:
          type: integer
          nullable: true
        page_end:
          type: integer
          nullable: true
    AssistantResponseMeta:
      type: object
      properties:
        latency_ms:
          type: integer
          nullable: true
        trace_id:
          type: string
        safety:
          type: object
    DocumentItem:
      type: object
      properties:
        doc_id:
          type: string
        name:
          type: string
        status:
          type: string
        product:
          type: string
          nullable: true
        version:
          type: string
          nullable: true
        tags:
          type: array
          items:
            type: string
        created_at:
          type: string
          format: date-time
          nullable: true
        updated_at:
          type: string
          format: date-time
          nullable: true
    DocumentDetail:
      allOf:
        - $ref: '#/components/schemas/DocumentItem'
        - type: object
          properties:
            pages:
              type: integer
              nullable: true
            sections:
              type: array
              items:
                type: object
                additionalProperties: true
    DocumentUploadResponse:
      type: object
      properties:
        doc_id:
          type: string
        status:
          type: string
    ErrorResponse:
      type: object
      properties:
        detail:
          type: object
          additionalProperties: true
```

## Комментарии для фронтенда
1. `meta.trace_id` из ответа ассистента сохраняем для саппорта и корреляции логов.
2. После `202 Accepted` загрузки нужно периодически запрашивать `/api/v1/documents/{doc_id}` или список документов, чтобы дождаться статуса `indexed`/`failed` (ingestion асинхронен).
3. В mock-режиме ответы могут быть пустыми/заглушками, но форма данных совпадает с продовой.
