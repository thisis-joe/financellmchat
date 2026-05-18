package com.example.financerag.document;

import com.example.financerag.common.ResourceNotFoundException;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.FileSystemResource;
import org.springframework.core.io.Resource;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Service
public class DocumentDownloadService {

    private static final Pattern SOURCE_FILE_PATTERN = Pattern.compile("^\\[출처파일]\\s*(.+)$", Pattern.MULTILINE);

    private final FinancialDocumentRepository documentRepository;
    private final Path rawPdfDirectory;

    public DocumentDownloadService(
            FinancialDocumentRepository documentRepository,
            @Value("${documents.raw-pdf-dir:data/raw/busanbank/product-disclosure/deposit/installment}") String rawPdfDirectory
    ) {
        this.documentRepository = documentRepository;
        this.rawPdfDirectory = Path.of(rawPdfDirectory).toAbsolutePath().normalize();
    }

    @Transactional(readOnly = true)
    public ResponseEntity<Resource> download(Long documentId) {
        FinancialDocument document = documentRepository.findById(documentId)
                .orElseThrow(() -> new ResourceNotFoundException("문서를 찾을 수 없습니다."));
        String fileName = sourceFileName(document);
        Path pdfPath = rawPdfDirectory.resolve(fileName).normalize();

        if (!pdfPath.startsWith(rawPdfDirectory) || !Files.isRegularFile(pdfPath)) {
            throw new ResourceNotFoundException("원본 PDF 파일을 찾을 수 없습니다.");
        }

        Resource resource = new FileSystemResource(pdfPath);
        ContentDisposition disposition = ContentDisposition.attachment()
                .filename(fileName, StandardCharsets.UTF_8)
                .build();

        return ResponseEntity.ok()
                .contentType(MediaType.APPLICATION_PDF)
                .header(HttpHeaders.CONTENT_DISPOSITION, disposition.toString())
                .body(resource);
    }

    private String sourceFileName(FinancialDocument document) {
        Matcher matcher = SOURCE_FILE_PATTERN.matcher(document.getContent());
        if (matcher.find()) {
            return Path.of(matcher.group(1).trim()).getFileName().toString();
        }
        return document.getTitle() + ".pdf";
    }
}
