package com.example.financerag.feedback;

import com.example.financerag.query.QueryHistory;
import com.example.financerag.query.QueryHistoryRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import static org.hamcrest.Matchers.containsString;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("h2")
class FeedbackApiControllerTest {

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
    void createFeedback() throws Exception {
        QueryHistory history = historyRepository.save(new QueryHistory("질문", "답변", "[]", "OK"));

        mockMvc.perform(post("/api/histories/{historyId}/feedback", history.getId())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "rating": "HELPFUL",
                                  "comment": "근거가 명확합니다"
                                }
                                """))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.historyId").value(history.getId()))
                .andExpect(jsonPath("$.rating").value("HELPFUL"))
                .andExpect(jsonPath("$.comment").value("근거가 명확합니다"));
    }

    @Test
    void createFeedbackReturns404WhenHistoryDoesNotExist() throws Exception {
        mockMvc.perform(post("/api/histories/{historyId}/feedback", 999L)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "rating": "NOT_HELPFUL"
                                }
                                """))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.message", containsString("질문 이력을 찾을 수 없습니다")));
    }

    @Test
    void createFeedbackValidatesRating() throws Exception {
        QueryHistory history = historyRepository.save(new QueryHistory("질문", "답변", "[]", "OK"));

        mockMvc.perform(post("/api/histories/{historyId}/feedback", history.getId())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "comment": "평가값 누락"
                                }
                                """))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message", containsString("rating")));
    }
}
