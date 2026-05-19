package com.example.financerag.rag;

import com.example.financerag.feedback.AnswerFeedbackRepository;
import com.example.financerag.query.QueryHistory;
import com.example.financerag.query.QueryHistoryRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import static org.hamcrest.Matchers.containsString;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("h2")
class RagEvidenceApiControllerTest {

    @Autowired
    MockMvc mockMvc;

    @Autowired
    QueryHistoryRepository historyRepository;

    @Autowired
    AnswerFeedbackRepository feedbackRepository;

    @BeforeEach
    void setUp() {
        feedbackRepository.deleteAll();
        historyRepository.deleteAll();
    }

    @Test
    void evidenceReturnsStoredCitationDebugInfo() throws Exception {
        QueryHistory history = historyRepository.save(new QueryHistory(
                "펫 적금 혜택 알려줘",
                "답변",
                """
                        [
                          {
                            "documentId": 1,
                            "title": "펫 적금 상품설명서",
                            "category": "예금상품>적립식예금",
                            "institution": "BNK부산은행",
                            "productName": "펫 적금",
                            "productType": "적립식예금",
                            "source": "PDF",
                            "sourceUrl": null,
                            "score": 0.91,
                            "snippet": "동물등록증 제출 시 우대이율을 확인합니다."
                          }
                        ]
                        """,
                "OK"
        ));

        mockMvc.perform(get("/api/histories/{historyId}/evidence", history.getId()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.historyId").value(history.getId()))
                .andExpect(jsonPath("$.question").value("펫 적금 혜택 알려줘"))
                .andExpect(jsonPath("$.evidences[0].rank").value(1))
                .andExpect(jsonPath("$.evidences[0].title").value("펫 적금 상품설명서"))
                .andExpect(jsonPath("$.evidences[0].score").value(0.91))
                .andExpect(jsonPath("$.summary", containsString("검색 근거 문서 1개")));
    }

    @Test
    void evidenceExplainsDirectAnswerWithoutSearchEvidence() throws Exception {
        QueryHistory history = historyRepository.save(new QueryHistory(
                "ㅎㅇ",
                "안녕하세요. 부산은행 적립식예금 상품공시 기준으로 도와드릴게요.",
                "[]",
                "DIRECT"
        ));

        mockMvc.perform(get("/api/histories/{historyId}/evidence", history.getId()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.evidences").isEmpty())
                .andExpect(jsonPath("$.summary", containsString("문서 검색이 필요하지 않아")));
    }

    @Test
    void evidenceReturns404WhenHistoryDoesNotExist() throws Exception {
        mockMvc.perform(get("/api/histories/{historyId}/evidence", 999L))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.message", containsString("질문 이력을 찾을 수 없습니다")));
    }
}
