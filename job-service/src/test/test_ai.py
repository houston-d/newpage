"""Unit tests for the ``ModelService`` class in ``app.api.ai``.

``ModelService`` wraps a HuggingFace text-generation pipeline behind a lock
and exposes three operations:

    class ModelService:
        def is_loaded(self) -> bool: ...
        def load_model(self, model: str) -> None: ...
        def generate_text(self, messages: list[dict[str, str]]) -> str: ...
"""

import json
from collections import Counter
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import torch
from app.api.ai import (
    ModelService,
    _build_job_index,
    _job_descriptions_dir,
    _job_to_search_text,
    _load_job_descriptions,
    _normalize_job,
    _rank_relevant_jobs,
    _tokenize,
)


@pytest.fixture()
def service() -> ModelService:
    """A fresh, unloaded ModelService instance for each test."""
    return ModelService()


class TestIsLoaded:
    """Tests for ModelService.is_loaded."""

    def test_returns_false_when_no_model_loaded(self, service: ModelService):
        """Core behaviour: a freshly constructed service has no pipeline."""
        assert service.is_loaded() is False

    def test_returns_true_after_pipe_is_set(self, service: ModelService):
        """Once a pipeline has been assigned internally, it reports loaded."""
        service._pipe = MagicMock()
        assert service.is_loaded() is True


class TestLoadModel:
    """Tests for ModelService.load_model."""

    def test_loads_pipeline_on_cpu_when_cuda_unavailable(self, service: ModelService):
        """When CUDA is unavailable, the pipeline should be built for CPU."""
        fake_pipe = MagicMock()
        with (
            patch("app.api.ai.torch.cuda.is_available", return_value=False),
            patch("app.api.ai.pipeline", return_value=fake_pipe) as mock_pipeline,
        ):
            service.load_model("TinyLlama/TinyLlama-1.1B-Chat-v1.0")

        mock_pipeline.assert_called_once_with(
            "text-generation",
            model="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
            dtype=torch.float32,
            device_map=None,
        )
        assert service.is_loaded() is True

    def test_loads_pipeline_on_gpu_when_cuda_available(self, service: ModelService):
        """When CUDA is available, bfloat16 and auto device_map should be used."""
        fake_pipe = MagicMock()
        with (
            patch("app.api.ai.torch.cuda.is_available", return_value=True),
            patch("app.api.ai.pipeline", return_value=fake_pipe) as mock_pipeline,
        ):
            service.load_model("TinyLlama/TinyLlama-1.1B-Chat-v1.0")

        mock_pipeline.assert_called_once_with(
            "text-generation",
            model="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
            dtype=torch.bfloat16,
            device_map="auto",
        )
        assert service.is_loaded() is True

    def test_propagates_exception_and_leaves_service_unloaded(self, service: ModelService):
        """If pipeline construction fails, the error should propagate and no pipe is stored."""
        with (
            patch("app.api.ai.torch.cuda.is_available", return_value=False),
            patch("app.api.ai.pipeline", side_effect=OSError("model not found")),
        ):
            with pytest.raises(OSError, match="model not found"):
                service.load_model("bad/model")

        assert service.is_loaded() is False

    def test_replaces_previously_loaded_pipeline(self, service: ModelService):
        """Loading a new model should overwrite any previously stored pipeline."""
        first_pipe = MagicMock()
        second_pipe = MagicMock()
        with patch("app.api.ai.torch.cuda.is_available", return_value=False):
            with patch("app.api.ai.pipeline", return_value=first_pipe):
                service.load_model("TinyLlama/TinyLlama-1.1B-Chat-v1.0")
            with patch("app.api.ai.pipeline", return_value=second_pipe):
                service.load_model("TinyLlama/TinyLlama-1.1B-Chat-v1.0")

        assert service._pipe is second_pipe


class TestGenerateText:
    """Tests for ModelService.generate_text."""

    def test_raises_runtime_error_when_model_not_loaded(self, service: ModelService):
        """generate_text must fail fast if no pipeline has been loaded."""
        with pytest.raises(RuntimeError, match="Model not loaded"):
            service.generate_text([{"role": "user", "content": "hi"}])

    def test_returns_generated_text_from_pipeline_output(self, service: ModelService):
        """Core behaviour: extracts generated_text from the first output element."""
        fake_pipe = MagicMock()
        fake_pipe.tokenizer.apply_chat_template.return_value = "rendered-prompt"
        fake_pipe.return_value = [{"generated_text": "Hello, world!"}]
        service._pipe = fake_pipe

        messages = [{"role": "user", "content": "Say hello"}]
        result = service.generate_text(messages)

        assert result == "Hello, world!"

    def test_applies_chat_template_with_expected_arguments(self, service: ModelService):
        """The chat template should be rendered with tokenize disabled and a generation prompt added."""
        fake_pipe = MagicMock()
        fake_pipe.tokenizer.apply_chat_template.return_value = "rendered-prompt"
        fake_pipe.return_value = [{"generated_text": "ok"}]
        service._pipe = fake_pipe

        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Say hello"},
        ]
        service.generate_text(messages)

        fake_pipe.tokenizer.apply_chat_template.assert_called_once_with(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

    def test_invokes_pipeline_with_rendered_prompt_and_no_full_text(self, service: ModelService):
        """The pipeline call should pass the rendered prompt and suppress echoing the input."""
        fake_pipe = MagicMock()
        fake_pipe.tokenizer.apply_chat_template.return_value = "rendered-prompt"
        fake_pipe.return_value = [{"generated_text": "ok"}]
        service._pipe = fake_pipe

        service.generate_text([{"role": "user", "content": "hi"}])

        args, kwargs = fake_pipe.call_args
        assert args[0] == "rendered-prompt"
        assert kwargs["return_full_text"] is False

    def test_propagates_exception_raised_by_pipeline(self, service: ModelService):
        """Errors from the underlying pipeline call should not be swallowed."""
        fake_pipe = MagicMock()
        fake_pipe.tokenizer.apply_chat_template.return_value = "rendered-prompt"
        fake_pipe.side_effect = ValueError("generation failed")
        service._pipe = fake_pipe

        with pytest.raises(ValueError, match="generation failed"):
            service.generate_text([{"role": "user", "content": "hi"}])

    def test_handles_empty_messages_list(self, service: ModelService):
        """An empty messages list should still be forwarded to the chat template unchanged."""
        fake_pipe = MagicMock()
        fake_pipe.tokenizer.apply_chat_template.return_value = "rendered-prompt"
        fake_pipe.return_value = [{"generated_text": "empty response"}]
        service._pipe = fake_pipe

        result = service.generate_text([])

        fake_pipe.tokenizer.apply_chat_template.assert_called_once_with(
            [],
            tokenize=False,
            add_generation_prompt=True,
        )
        assert result == "empty response"


class TestJobDescriptionsDir:
    """Tests for _job_descriptions_dir."""

    def test_returns_path_object(self):
        """Core behaviour: the function returns a Path instance."""
        result = _job_descriptions_dir()
        assert isinstance(result, Path)

    def test_path_ends_with_expected_resource_segments(self):
        """The returned path should point at resources/job-descriptions."""
        result = _job_descriptions_dir()
        assert result.parts[-2:] == ("resources", "job-descriptions")

    def test_path_is_absolute(self):
        """The directory is resolved relative to the module file, so it must be absolute."""
        result = _job_descriptions_dir()
        assert result.is_absolute()

    def test_returns_same_path_on_repeated_calls(self):
        """Calling the function multiple times should be deterministic."""
        assert _job_descriptions_dir() == _job_descriptions_dir()


class TestTokenize:
    """Tests for _tokenize."""

    def test_splits_on_whitespace_and_lowercases(self):
        """Core behaviour: words are lowercased and split into tokens."""
        assert _tokenize("Senior Python Developer") == ["senior", "python", "developer"]

    def test_strips_punctuation_between_words(self):
        """Punctuation should not be included, and words should still separate correctly."""
        assert _tokenize("C++/Python, Go & Rust!") == ["c", "python", "go", "rust"]

    def test_keeps_alphanumeric_tokens_together(self):
        """Alphanumeric substrings such as 'python3' should remain a single token."""
        assert _tokenize("python3 developer") == ["python3", "developer"]

    def test_returns_empty_list_for_empty_string(self):
        """Boundary case: an empty string yields no tokens."""
        assert _tokenize("") == []

    def test_returns_empty_list_when_no_alphanumeric_characters(self):
        """A string containing only punctuation/whitespace has no tokens."""
        assert _tokenize("   ---***   ") == []

    def test_handles_numbers_and_mixed_case(self):
        """Numbers and mixed-case text are tokenized correctly."""
        assert _tokenize("Salary £50000 - £60000") == ["salary", "50000", "60000"]


class TestNormalizeJob:
    """Tests for _normalize_job."""

    def test_normalizes_complete_raw_job(self):
        """Core behaviour: a fully populated raw job dict maps to the expected shape."""
        raw_job = {
            "title": "Software Engineer",
            "location": "London",
            "company": "Acme Corp",
            "salary": "£50,000",
            "jd": "Build great software.",
        }

        result = _normalize_job(raw_job, "job-1.json")

        assert result == {
            "id": "job-1",
            "title": "Software Engineer",
            "location": "London",
            "company": "Acme Corp",
            "salary": "£50,000",
            "jd": "Build great software.",
            "source_file": "job-1.json",
        }

    def test_missing_fields_default_to_empty_strings(self):
        """Fields absent from the raw job should default to empty strings, not raise."""
        result = _normalize_job({}, "job-2.json")

        assert result["title"] == ""
        assert result["location"] == ""
        assert result["company"] == ""
        assert result["salary"] == ""
        assert result["jd"] == ""
        assert result["source_file"] == "job-2.json"

    def test_strips_surrounding_whitespace(self):
        """Leading/trailing whitespace in string fields should be stripped."""
        raw_job = {"title": "  Data Scientist  ", "location": "\tRemote\n"}

        result = _normalize_job(raw_job, "job-3.json")

        assert result["title"] == "Data Scientist"
        assert result["location"] == "Remote"

    def test_non_string_values_are_coerced_to_strings(self):
        """Non-string raw values (e.g. numbers) should be converted via str()."""
        raw_job = {"salary": 75000, "title": None}

        result = _normalize_job(raw_job, "job-4.json")

        assert result["salary"] == "75000"
        # str(None) == "None", then stripped
        assert result["title"] == "None"

    def test_extra_unrecognized_keys_are_ignored(self):
        """Keys not part of the known schema should be silently dropped."""
        raw_job = {
            "title": "QA Engineer",
            "unexpected_field": "should not appear",
        }

        result = _normalize_job(raw_job, "job-5.json")

        assert "unexpected_field" not in result
        assert set(result.keys()) == {"id", "title", "location", "company", "salary", "jd", "source_file"}


class TestLoadJobDescriptions:
    """Tests for _load_job_descriptions."""

    def _write_job(self, directory: Path, filename: str, data: dict) -> None:
        (directory / filename).write_text(json.dumps(data), encoding="utf-8")

    def test_loads_and_normalizes_all_json_files_in_directory(self, tmp_path: Path):
        """Core behaviour: every *.json file in the directory is read and normalized."""
        self._write_job(
            tmp_path,
            "job-a.json",
            {"title": "Backend Engineer", "location": "Leeds", "company": "Foo Ltd", "salary": "£40k", "jd": "Do stuff."},
        )
        self._write_job(
            tmp_path,
            "job-b.json",
            {"title": "Frontend Engineer", "location": "Remote", "company": "Bar Inc", "salary": "", "jd": "Build UI."},
        )

        with patch("app.api.ai._job_descriptions_dir", return_value=tmp_path):
            jobs = _load_job_descriptions()

        assert len(jobs) == 2
        assert jobs[0]["title"] == "Backend Engineer"
        assert jobs[0]["source_file"] == "job-a.json"
        assert jobs[1]["title"] == "Frontend Engineer"
        assert jobs[1]["source_file"] == "job-b.json"

    def test_returns_jobs_sorted_by_filename(self, tmp_path: Path):
        """Files should be processed in sorted filename order, not creation order."""
        self._write_job(tmp_path, "z-job.json", {"title": "Z Job"})
        self._write_job(tmp_path, "a-job.json", {"title": "A Job"})

        with patch("app.api.ai._job_descriptions_dir", return_value=tmp_path):
            jobs = _load_job_descriptions()

        assert [job["source_file"] for job in jobs] == ["a-job.json", "z-job.json"]

    def test_raises_file_not_found_error_when_directory_missing(self, tmp_path: Path):
        """If the job descriptions directory doesn't exist, a clear error should be raised."""
        missing_dir = tmp_path / "does-not-exist"

        with patch("app.api.ai._job_descriptions_dir", return_value=missing_dir):
            with pytest.raises(FileNotFoundError, match="Job descriptions directory not found"):
                _load_job_descriptions()

    def test_raises_value_error_when_no_json_files_present(self, tmp_path: Path):
        """An existing but empty directory should raise a ValueError, not return an empty list."""
        (tmp_path / "notes.txt").write_text("not a job", encoding="utf-8")

        with patch("app.api.ai._job_descriptions_dir", return_value=tmp_path):
            with pytest.raises(ValueError, match="No job description files found"):
                _load_job_descriptions()

    def test_propagates_json_decode_error_for_malformed_file(self, tmp_path: Path):
        """Malformed JSON in a job file should surface as a JSONDecodeError, not be swallowed."""
        (tmp_path / "broken.json").write_text("{not valid json", encoding="utf-8")

        with patch("app.api.ai._job_descriptions_dir", return_value=tmp_path):
            with pytest.raises(json.JSONDecodeError):
                _load_job_descriptions()

    def test_missing_fields_in_raw_job_default_to_empty_strings(self, tmp_path: Path):
        """Jobs with sparse fields should still be normalized without raising."""
        self._write_job(tmp_path, "sparse.json", {"title": "Data Analyst"})

        with patch("app.api.ai._job_descriptions_dir", return_value=tmp_path):
            jobs = _load_job_descriptions()

        assert jobs[0]["location"] == ""
        assert jobs[0]["company"] == ""
        assert jobs[0]["salary"] == ""
        assert jobs[0]["jd"] == ""

    def test_ignores_non_json_files_in_directory(self, tmp_path: Path):
        """Files without a .json extension should not be picked up by the glob."""
        self._write_job(tmp_path, "job.json", {"title": "Only Job"})
        (tmp_path / "readme.md").write_text("ignore me", encoding="utf-8")

        with patch("app.api.ai._job_descriptions_dir", return_value=tmp_path):
            jobs = _load_job_descriptions()

        assert len(jobs) == 1
        assert jobs[0]["title"] == "Only Job"


class TestJobToSearchText:
    """Tests for _job_to_search_text."""

    def test_joins_fields_with_single_space(self):
        """Core behaviour: all five text fields are concatenated with single spaces."""
        job = {
            "title": "Software Engineer",
            "location": "London",
            "company": "Acme Corp",
            "salary": "£50,000",
            "jd": "Build great software.",
        }

        result = _job_to_search_text(job)

        assert result == "Software Engineer London Acme Corp £50,000 Build great software."

    def test_handles_empty_fields_without_raising(self):
        """Empty string fields should still produce a joinable result with extra spaces preserved."""
        job = {"title": "", "location": "", "company": "", "salary": "", "jd": ""}

        result = _job_to_search_text(job)

        assert result == "    "


class TestBuildJobIndex:
    """Tests for _build_job_index.

    ``_build_job_index`` is decorated with ``@lru_cache(maxsize=1)``, so the
    cache must be cleared before and after each test to avoid state leaking
    between tests (and across the module's real, uncached usage).
    """

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        """Ensure every test starts and ends with a clean lru_cache."""
        _build_job_index.cache_clear()
        yield
        _build_job_index.cache_clear()

    def _job(self, title="", location="", company="", salary="", jd="", source_file="job.json") -> dict[str, str]:
        return {
            "title": title,
            "location": location,
            "company": company,
            "salary": salary,
            "jd": jd,
            "source_file": source_file,
        }

    def test_builds_term_and_doc_frequencies_for_multiple_jobs(self):
        """Core behaviour: term frequencies per doc and doc frequencies across docs are computed."""
        jobs = (
            self._job(title="Python Developer", jd="Python and Django experience.", source_file="a.json"),
            self._job(title="Java Developer", jd="Java and Spring experience.", source_file="b.json"),
        )
        with patch("app.api.ai._load_job_descriptions_cached", return_value=jobs):
            doc_term_frequencies, doc_frequencies = _build_job_index()

        assert len(doc_term_frequencies) == 2
        # "developer" and "experience" appear in both docs.
        assert doc_frequencies["developer"] == 2
        assert doc_frequencies["experience"] == 2
        # "python" only appears in the first doc.
        assert doc_frequencies["python"] == 1
        assert doc_term_frequencies[0]["python"] == 2  # title + jd

    def test_returns_empty_structures_for_no_jobs(self):
        """Boundary case: an empty job list yields an empty tuple and an empty Counter."""
        with patch("app.api.ai._load_job_descriptions_cached", return_value=()):
            doc_term_frequencies, doc_frequencies = _build_job_index()

        assert doc_term_frequencies == ()
        assert doc_frequencies == Counter()

    def test_doc_frequency_counts_each_term_once_per_document(self):
        """A term repeated many times in one doc should still only add 1 to doc_frequencies."""
        jobs = (self._job(jd="python python python python", source_file="a.json"),)
        with patch("app.api.ai._load_job_descriptions_cached", return_value=jobs):
            doc_term_frequencies, doc_frequencies = _build_job_index()

        assert doc_term_frequencies[0]["python"] == 4
        assert doc_frequencies["python"] == 1

    def test_result_types_are_tuple_of_counters_and_counter(self):
        """Return shape must be (tuple[Counter, ...], Counter) as declared by the type hints."""
        jobs = (self._job(title="Engineer", source_file="a.json"),)
        with patch("app.api.ai._load_job_descriptions_cached", return_value=jobs):
            doc_term_frequencies, doc_frequencies = _build_job_index()

        assert isinstance(doc_term_frequencies, tuple)
        assert all(isinstance(tf, Counter) for tf in doc_term_frequencies)
        assert isinstance(doc_frequencies, Counter)

    def test_preserves_document_order(self):
        """The order of doc_term_frequencies must match the order jobs are returned in."""
        jobs = (
            self._job(title="First", source_file="a.json"),
            self._job(title="Second", source_file="b.json"),
            self._job(title="Third", source_file="c.json"),
        )
        with patch("app.api.ai._load_job_descriptions_cached", return_value=jobs):
            doc_term_frequencies, _ = _build_job_index()

        assert list(doc_term_frequencies[0]) == ["first"]
        assert list(doc_term_frequencies[1]) == ["second"]
        assert list(doc_term_frequencies[2]) == ["third"]

    def test_result_is_cached_and_source_loaded_only_once(self):
        """Subsequent calls should hit the lru_cache instead of recomputing/reloading."""
        jobs = (self._job(title="Cached Job", source_file="a.json"),)
        with patch("app.api.ai._load_job_descriptions_cached", return_value=jobs) as mock_load:
            first_result = _build_job_index()
            second_result = _build_job_index()

        mock_load.assert_called_once()
        assert first_result is second_result

    def test_handles_jobs_with_no_shared_terms(self):
        """Distinct vocabularies across jobs should not cross-pollute doc frequencies."""
        jobs = (
            self._job(title="Chef", jd="Cook great food.", source_file="a.json"),
            self._job(title="Pilot", jd="Fly airplanes safely.", source_file="b.json"),
        )
        with patch("app.api.ai._load_job_descriptions_cached", return_value=jobs):
            doc_term_frequencies, doc_frequencies = _build_job_index()

        assert doc_frequencies["chef"] == 1
        assert doc_frequencies["pilot"] == 1
        assert "chef" not in doc_term_frequencies[1]
        assert "pilot" not in doc_term_frequencies[0]


class TestRankRelevantJobs:
    """Tests for _rank_relevant_jobs.

    ``_rank_relevant_jobs`` now delegates ranking to the Qdrant-backed
    vector database and falls back to input ordering when needed.
    """

    def _job(self, title="", location="", company="", salary="", jd="", source_file="job.json") -> dict[str, str]:
        return {
            "title": title,
            "location": location,
            "company": company,
            "salary": salary,
            "jd": jd,
            "source_file": source_file,
        }

    def test_ranks_jobs_by_relevance_to_query(self):
        """Core behaviour: returns jobs in the order provided by vector search."""
        jobs = [
            self._job(title="Python Developer", jd="Python and Django experience.", source_file="a.json"),
            self._job(title="Java Developer", jd="Java and Spring experience.", source_file="b.json"),
        ]
        ranked = [jobs[1], jobs[0]]
        with patch("app.api.ai.job_vector_database.search", return_value=ranked):
            result = _rank_relevant_jobs("python django", jobs, top_k=2)

        assert [job["source_file"] for job in result] == ["b.json", "a.json"]

    def test_higher_scoring_job_ranks_before_lower_scoring_job(self):
        """For tokenizable queries, vector search is invoked with the requested top_k."""
        jobs = [
            self._job(title="Java Developer", jd="Some Python exposure.", source_file="weak-match.json"),
            self._job(title="Python Developer", jd="Python Python Django Django experience.", source_file="strong-match.json"),
        ]
        with patch("app.api.ai.job_vector_database.search", return_value=jobs) as mock_search:
            _rank_relevant_jobs("python django", jobs, top_k=2)

        mock_search.assert_called_once_with("python django", 2)

    def test_empty_query_returns_first_top_k_jobs_unranked(self):
        """Boundary case: a query with no tokenizable terms falls back to the input order, sliced."""
        jobs = [
            self._job(title="First", source_file="a.json"),
            self._job(title="Second", source_file="b.json"),
            self._job(title="Third", source_file="c.json"),
        ]

        result = _rank_relevant_jobs("   !!! ", jobs, top_k=2)

        assert result == jobs[:2]

    def test_vector_search_failure_falls_back_to_first_top_k_jobs(self):
        """If vector search fails, fall back to input order."""
        jobs = [
            self._job(title="Chef", jd="Cook great food.", source_file="a.json"),
            self._job(title="Pilot", jd="Fly airplanes safely.", source_file="b.json"),
        ]
        with patch("app.api.ai.job_vector_database.search", side_effect=RuntimeError("search failed")):
            result = _rank_relevant_jobs("astronaut", jobs, top_k=2)

        assert result == jobs[:2]

    def test_top_k_limits_number_of_results(self):
        """top_k must cap the number of returned jobs even when many jobs match."""
        jobs = [
            self._job(title="Python Developer A", jd="Python experience.", source_file="a.json"),
            self._job(title="Python Developer B", jd="Python experience.", source_file="b.json"),
            self._job(title="Python Developer C", jd="Python experience.", source_file="c.json"),
        ]
        with patch("app.api.ai.job_vector_database.search", return_value=jobs):
            result = _rank_relevant_jobs("python", jobs, top_k=1)

        assert len(result) == 1

    def test_top_k_zero_returns_empty_list(self):
        """Boundary case: top_k=0 should return no jobs at all, regardless of scores."""
        jobs = [self._job(title="Python Developer", jd="Python experience.", source_file="a.json")]
        result = _rank_relevant_jobs("python", jobs, top_k=0)

        assert result == []

    def test_empty_jobs_list_returns_empty_list(self):
        """Boundary case: an empty jobs list should return an empty list on vector-search failure."""
        with patch("app.api.ai.job_vector_database.search", side_effect=RuntimeError("not loaded")):
            result = _rank_relevant_jobs("python", [], top_k=5)

        assert result == []

    def test_empty_vector_results_fall_back_to_first_top_k_jobs(self):
        """If vector search returns no hits, fallback ordering is used."""
        jobs = [
            self._job(title="Python Developer", jd="Python experience.", source_file="a.json"),
            self._job(title="Go Developer", jd="Go experience.", source_file="b.json"),
        ]
        with patch("app.api.ai.job_vector_database.search", return_value=[]):
            result = _rank_relevant_jobs("python kubernetes", jobs, top_k=1)

        assert result == jobs[:1]
