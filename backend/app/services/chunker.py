import os
import logging
from pathlib import Path
from typing import List

logger = logging.getLogger("cyberverse.chunker")


class RepositoryChunker:
    @staticmethod
    def chunk_repository(repo_path: str, chunk_size: int = 7000) -> List[str]:
        """
        Recursively reads all target code files in a repository and splits them into
        chunks of up to chunk_size characters, including filename metadata.
        """
        logger.info("Initializing codebase chunking for target path: %s", repo_path)
        chunks = []
        target_extensions = {".py", ".js", ".ts", ".tsx", ".jsx"}
        ignored_dirs = {"node_modules", "venv", ".git", "__pycache__"}

        repo_root = Path(repo_path).resolve()

        if repo_root.is_file():
            if repo_root.suffix.lower() in target_extensions:
                chunks.extend(RepositoryChunker._chunk_file(repo_root, repo_root, chunk_size))
            return chunks

        for root, dirs, files in os.walk(repo_root):
            # Prune ignored directories in-place to avoid unnecessary traversal
            dirs[:] = [d for d in dirs if d not in ignored_dirs]
            
            for file in files:
                file_path = Path(root) / file
                if file_path.suffix.lower() in target_extensions:
                    chunks.extend(RepositoryChunker._chunk_file(file_path, repo_root, chunk_size))
                    
        logger.info("Codebase chunking finished. Generated %d chunks.", len(chunks))
        return chunks

    @staticmethod
    def _chunk_file(file_path: Path, repo_root: Path, chunk_size: int) -> List[str]:
        chunks = []
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            
            if not content.strip():
                return chunks

            rel_path = os.path.relpath(str(file_path), str(repo_root))
            
            total_len = len(content)
            start = 0
            while start < total_len:
                end = min(start + chunk_size, total_len)
                chunk_text = content[start:end]
                
                formatted_chunk = f"FILE: {rel_path}\n\n{chunk_text}"
                chunks.append(formatted_chunk)
                start = end
        except Exception as e:
            logger.warning("Failed to chunk file %s: %s", file_path, e)
        return chunks
