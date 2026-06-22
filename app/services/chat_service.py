from __future__ import annotations

import json
import logging
from typing import Any
from uuid import uuid4

from app.core.exceptions import AppError
from app.domain.chat_intent import ChatIntent
from app.schemas.chat import ChatQueryRequest, ChatQueryResponse, ChatSource
from app.schemas.rag import RAGQueryRequest
from app.services.analytics_service import AnalyticsService
from app.services.intent_router import route_intent
from app.services.llm_service import CHAT_SYSTEM_INSTRUCTIONS, LLMService
from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(
        self,
        rag_service: RAGService | None,
        analytics_service: AnalyticsService,
        llm_service: LLMService | None,
    ) -> None:
        self.rag_service = rag_service
        self.analytics_service = analytics_service
        self.llm_service = llm_service
        self._conversations: dict[str, list[dict[str, str]]] = {}

    def _get_history(self, conv_id: str) -> list[dict[str, str]]:
        return self._conversations.get(conv_id, [])[-10:]

    def _append_turn(self, conv_id: str, user_msg: str, assistant_msg: str) -> None:
        if conv_id not in self._conversations:
            self._conversations[conv_id] = []
        self._conversations[conv_id].append({"user": user_msg, "assistant": assistant_msg})
        if len(self._conversations[conv_id]) > 10:
            self._conversations[conv_id] = self._conversations[conv_id][-10:]

    async def query(self, request: ChatQueryRequest) -> ChatQueryResponse:
        intent = route_intent(request.message)
        conv_id = str(request.conversation_id) if request.conversation_id else str(uuid4())

        # Jika intent analytics tapi tidak ada dataset_id, coba ambil dataset terbaru
        if (
            intent
            in {
                ChatIntent.ANALYTICS_SUMMARY,
                ChatIntent.ANALYTICS_ANOMALY,
                ChatIntent.ANALYTICS_TREND,
                ChatIntent.COMBINED,
            }
            and request.dataset_id is None
        ):
            latest = await self.analytics_service.repository.get_with_rows(None)
            if latest is None:
                raise AppError(
                    "DATASET_REQUIRED",
                    "Pilih dataset terlebih dahulu untuk menanyakan data analytics.",
                    status_code=400,
                )
            request = ChatQueryRequest(
                message=request.message,
                dataset_id=latest.id,
                document_ids=request.document_ids,
                conversation_id=request.conversation_id,
            )

        if intent == ChatIntent.SOP_QUESTION:
            response = await self._handle_sop(request, conv_id)
        elif intent == ChatIntent.ANALYTICS_SUMMARY:
            response = await self._handle_analytics_summary(request, conv_id)
        elif intent == ChatIntent.ANALYTICS_ANOMALY:
            response = await self._handle_analytics_anomaly(request, conv_id)
        elif intent == ChatIntent.ANALYTICS_TREND:
            response = await self._handle_analytics_trend(request, conv_id)
        elif intent == ChatIntent.COMBINED:
            response = await self._handle_combined(request, conv_id)
        else:
            response = ChatQueryResponse(
                answer=(
                    "Maaf, saya belum dapat memahami pertanyaan tersebut. "
                    "Coba tanyakan tentang SOP atau data analytics."
                ),
                intent=ChatIntent.UNSUPPORTED,
                tools_used=[],
                sources=[],
                warnings=[],
            )

        self._append_turn(conv_id, request.message, response.answer)
        response.conversation_id = conv_id
        return response

    async def _handle_sop(self, request: ChatQueryRequest, conv_id: str) -> ChatQueryResponse:
        if self.rag_service is None:
            return ChatQueryResponse(
                answer="Layanan SOP tidak tersedia saat ini.",
                intent=ChatIntent.SOP_QUESTION,
                tools_used=["search_sop"],
                sources=[],
                warnings=["RAG service tidak tersedia."],
            )

        history = self._get_history(conv_id)
        history_str = ""
        if history:
            lines = []
            for turn in history:
                lines.append(f"User: {turn['user']}")
                lines.append(f"Assistant: {turn['assistant']}")
            history_str = "\n".join(lines)

        rag_request = RAGQueryRequest(
            question=request.message,
            document_ids=(
                [str(did) for did in request.document_ids] if request.document_ids else None
            ),
            top_k=3,
            generate_answer=True,
            conversation_history=history_str or None,
        )
        rag_response = await self.rag_service.query(rag_request)

        sources: list[ChatSource] = []
        for ctx in rag_response.contexts:
            if ctx.used_for_generation:
                sources.append(
                    ChatSource(
                        type="document",
                        label=(
                            ctx.metadata.heading_path[-1]
                            if ctx.metadata.heading_path
                            else ctx.metadata.filename
                        ),
                        document_id=ctx.document_id,
                        filename=ctx.metadata.filename,
                        heading=(
                            " > ".join(ctx.metadata.heading_path)
                            if ctx.metadata.heading_path
                            else None
                        ),
                        chunk_id=ctx.chunk_id,
                        relevance_score=round(ctx.scores.final, 6),
                    )
                )

        warnings: list[str] = []
        if not rag_response.contexts:
            warnings.append("Tidak ada context yang melewati minimum relevance score.")

        answer = rag_response.answer or (
            "Informasi tersebut tidak ditemukan dalam dokumen SOP yang tersedia."
        )
        return ChatQueryResponse(
            answer=answer,
            intent=ChatIntent.SOP_QUESTION,
            tools_used=["search_sop"],
            sources=sources,
            warnings=warnings,
        )

    async def _handle_analytics_summary(
        self, request: ChatQueryRequest, conv_id: str
    ) -> ChatQueryResponse:
        dataset_id = str(request.dataset_id) if request.dataset_id else None
        summary = await self.analytics_service.summary(dataset_id)
        data = self._format_analytics_summary(summary)
        prompt = self._build_analytics_prompt(request.message, data)
        answer = await self._llm_chat(prompt, conv_id=conv_id)

        sources = [
            ChatSource(
                type="analytics",
                label=summary["dataset"]["filename"],
                dataset_id=request.dataset_id,
                filename=summary["dataset"]["filename"],
            )
        ]

        return ChatQueryResponse(
            answer=answer,
            intent=ChatIntent.ANALYTICS_SUMMARY,
            tools_used=["get_analytics_summary"],
            sources=sources,
            warnings=[],
        )

    async def _handle_analytics_anomaly(
        self, request: ChatQueryRequest, conv_id: str
    ) -> ChatQueryResponse:
        dataset_id = str(request.dataset_id) if request.dataset_id else None
        summary = await self.analytics_service.summary(dataset_id)
        anomalies = summary.get("anomalies", [])
        data = {"anomalies": anomalies, "dataset": summary["dataset"]}
        prompt = self._build_analytics_prompt(request.message, data)
        answer = await self._llm_chat(prompt, conv_id=conv_id)

        sources = [
            ChatSource(
                type="analytics",
                label=summary["dataset"]["filename"],
                dataset_id=request.dataset_id,
                filename=summary["dataset"]["filename"],
            )
        ]

        warnings = []
        if anomalies:
            warnings.append(
                "Anomali perlu direview dan tidak otomatis dianggap sebagai data salah."
            )

        return ChatQueryResponse(
            answer=answer,
            intent=ChatIntent.ANALYTICS_ANOMALY,
            tools_used=["get_analytics_anomalies"],
            sources=sources,
            warnings=warnings,
        )

    async def _handle_analytics_trend(
        self, request: ChatQueryRequest, conv_id: str
    ) -> ChatQueryResponse:
        dataset_id = str(request.dataset_id) if request.dataset_id else None
        summary = await self.analytics_service.summary(dataset_id)
        weekly = summary.get("weekly_trend", [])
        data = {
            "weekly_trend": weekly,
            "dataset": summary["dataset"],
            "metrics": summary["metrics"],
        }
        prompt = self._build_analytics_prompt(request.message, data)
        answer = await self._llm_chat(prompt, conv_id=conv_id)

        sources = [
            ChatSource(
                type="analytics",
                label=summary["dataset"]["filename"],
                dataset_id=request.dataset_id,
                filename=summary["dataset"]["filename"],
            )
        ]

        return ChatQueryResponse(
            answer=answer,
            intent=ChatIntent.ANALYTICS_TREND,
            tools_used=["get_weekly_trend"],
            sources=sources,
            warnings=[],
        )

    async def _handle_combined(self, request: ChatQueryRequest, conv_id: str) -> ChatQueryResponse:
        dataset_id = str(request.dataset_id) if request.dataset_id else None
        analytics_summary = await self.analytics_service.summary(dataset_id)
        analytics_data = self._format_analytics_summary(analytics_summary)

        rag_contexts: list[dict[str, Any]] = []
        if self.rag_service is not None:
            rag_request = RAGQueryRequest(
                question=request.message,
                document_ids=(
                    [str(did) for did in request.document_ids] if request.document_ids else None
                ),
                top_k=3,
                generate_answer=False,
            )
            rag_response = await self.rag_service.query(rag_request)
            for ctx in rag_response.contexts:
                if ctx.meets_minimum_score:
                    heading = (
                        " > ".join(ctx.metadata.heading_path) if ctx.metadata.heading_path else ""
                    )
                    rag_contexts.append(
                        {
                            "content": ctx.content,
                            "filename": ctx.metadata.filename,
                            "heading": heading,
                        }
                    )

        prompt = self._build_combined_prompt(request.message, analytics_data, rag_contexts)
        answer = await self._llm_chat(prompt, conv_id=conv_id)

        sources: list[ChatSource] = [
            ChatSource(
                type="analytics",
                label=analytics_summary["dataset"]["filename"],
                dataset_id=request.dataset_id,
                filename=analytics_summary["dataset"]["filename"],
            )
        ]
        for ctx in rag_contexts:
            sources.append(
                ChatSource(
                    type="document",
                    label=ctx["heading"] or ctx["filename"],
                    filename=ctx["filename"],
                    heading=ctx["heading"] or None,
                )
            )

        warnings = [
            "Data menunjukkan pola pada tanggal tertentu. "
            "Dokumen SOP yang tersedia menjelaskan aturan performa SPG, "
            "tetapi data ini belum cukup untuk menyimpulkan hubungan sebab-akibat."
        ]

        return ChatQueryResponse(
            answer=answer,
            intent=ChatIntent.COMBINED,
            tools_used=["get_analytics_summary", "search_sop"],
            sources=sources,
            warnings=warnings,
        )

    @staticmethod
    def _format_analytics_summary(summary: dict[str, Any]) -> dict[str, Any]:
        return {
            "dataset": summary["dataset"],
            "metrics": summary["metrics"],
            "weekly_trend": summary.get("weekly_trend", []),
            "anomalies": summary.get("anomalies", []),
            "daily_records": summary.get("daily_records", []),
        }

    @staticmethod
    def _build_analytics_prompt(message: str, data: dict[str, Any]) -> str:
        return (
            f"Pertanyaan user:\n{message}\n\n"
            f"Data analytics:\n{json.dumps(data, indent=2, default=str)}"
        )

    @staticmethod
    def _build_combined_prompt(
        message: str,
        analytics_data: dict[str, Any],
        rag_contexts: list[dict[str, Any]],
    ) -> str:
        parts = [
            f"Pertanyaan user:\n{message}",
            f"\nData analytics:\n{json.dumps(analytics_data, indent=2, default=str)}",
        ]
        if rag_contexts:
            parts.append(f"\nKonteks SOP:\n{json.dumps(rag_contexts, indent=2, default=str)}")
        return "\n".join(parts)

    async def _llm_chat(self, prompt: str, conv_id: str | None = None) -> str:
        if self.llm_service is None:
            return "Maaf, layanan AI tidak tersedia saat ini."
        full_prompt = prompt
        if conv_id:
            history = self._get_history(conv_id)
            if history:
                lines = []
                for turn in history:
                    lines.append(f"User: {turn['user']}")
                    lines.append(f"Assistant: {turn['assistant']}")
                history_block = "\n".join(lines)
                full_prompt = f"Riwayat percakapan sebelumnya:\n{history_block}\n\n{full_prompt}"
        try:
            return await self.llm_service.generate(CHAT_SYSTEM_INSTRUCTIONS, full_prompt)
        except Exception:
            logger.exception("LLM chat generation failed")
            return "Maaf, terjadi kesalahan saat memproses jawaban. Silakan coba lagi."
