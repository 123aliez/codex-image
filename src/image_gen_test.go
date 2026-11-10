package main

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"image"
	"image/jpeg"
	"image/png"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestSelectAvailableModel(t *testing.T) {
	for _, test := range []struct {
		name, requested string
		explicit        bool
		models          []string
		want            string
		fail            bool
	}{
		{"default flare", "", false, []string{"gpt-image-2", "gpt-image-2.5-flare", "gpt-image-2.6-flare"}, "gpt-image-2.5-flare", false},
		{"other flare", "", false, []string{"gpt-image-2", "gpt-image-2.6-flare"}, "gpt-image-2.6-flare", false},
		{"no silent non-flare fallback", "", false, []string{"gpt-image-2"}, "", true},
		{"explicit model", "Image 2", true, []string{"gpt-image-2", "gpt-image-2.5-flare"}, "gpt-image-2", false},
		{"unavailable explicit model", "gpt-image-2.5", true, []string{"gpt-image-2.5-flare"}, "", true},
		{"gateway ID", "gpt-image-2.6-sunburst", true, []string{"gpt-image-2.6-sunburst"}, "gpt-image-2.6-sunburst", false},
		{"video rejected", "grok-video-flare", true, []string{"grok-video-flare"}, "", true},
	} {
		t.Run(test.name, func(t *testing.T) {
			got, err := selectAvailableModel(test.requested, test.explicit, test.models)
			if (err != nil) != test.fail || got != test.want {
				t.Fatalf("got %q, error %v; want %q, fail %v", got, err, test.want, test.fail)
			}
		})
	}
}

func TestModelListUsesCurrentEndpointAndKey(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet || r.URL.Path != "/v1/models" || r.Header.Get("Authorization") != "Bearer test-key" {
			t.Errorf("incorrect model-list request: %s %s", r.Method, r.URL.Path)
		}
		io.WriteString(w, `{"data":[{"id":"gpt-image-2.5-flare"},{"id":"gpt-image-2"},{"id":"gpt-image-2.5-flare"}]}`)
	}))
	defer server.Close()
	t.Setenv("CODEX_API_URL", server.URL+"/v1")
	t.Setenv("CODEX_API_KEY", "test-key")
	models, err := availableModels()
	if err != nil || strings.Join(models, ",") != "gpt-image-2,gpt-image-2.5-flare" {
		t.Fatalf("models %v, error %v", models, err)
	}
}

func TestMalformedHTTPFramingKeepsCompleteJSON(t *testing.T) {
	body := `{"data":[{"b64_json":"aW1hZ2U="}]}`
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Length", "1000")
		io.WriteString(w, body)
	}))
	defer server.Close()
	got, err := doRequest(server.Client(), func() (*http.Request, error) {
		return http.NewRequest(http.MethodPost, server.URL, strings.NewReader(`{}`))
	}, 3)
	if err != nil || string(got) != body {
		t.Fatalf("lost complete JSON response: %q, error %v", got, err)
	}
}

func TestTruncatedResponseIsNotRetried(t *testing.T) {
	requests := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests++
		w.Header().Set("Content-Length", "1000")
		io.WriteString(w, `{"data":[{"b64_json":"truncated`)
	}))
	defer server.Close()
	_, err := doRequest(server.Client(), func() (*http.Request, error) {
		return http.NewRequest(http.MethodPost, server.URL, strings.NewReader(`{}`))
	}, 3)
	if err == nil || !strings.Contains(err.Error(), "HTTP 200") || !strings.Contains(err.Error(), "unexpected EOF") || !strings.Contains(err.Error(), "do not resubmit automatically") {
		t.Fatalf("missing actionable response error: %v", err)
	}
	if requests != 1 {
		t.Fatalf("sent %d generation requests after ambiguous success", requests)
	}
}

func TestBatchValidatesAllModelsBeforeAnyGeneration(t *testing.T) {
	posts := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodGet {
			io.WriteString(w, `{"data":[{"id":"gpt-image-2.5-flare"}]}`)
		} else {
			posts++
			http.Error(w, "must not generate", 500)
		}
	}))
	defer server.Close()
	t.Setenv("CODEX_API_URL", server.URL)
	t.Setenv("CODEX_API_KEY", "test-key")
	path := filepath.Join(t.TempDir(), "jobs.jsonl")
	if err := os.WriteFile(path, []byte("{\"prompt\":\"cup\"}\n{\"prompt\":\"kite\",\"model\":\"unlisted-model\"}\n"), 0600); err != nil {
		t.Fatal(err)
	}
	err := runBatch([]string{"--input", path})
	if err == nil || !strings.Contains(err.Error(), "batch job 2") || posts != 0 {
		t.Fatalf("invalid batch was partially submitted: posts %d, error %v", posts, err)
	}
}

func TestEditUploadsImageMIMETypes(t *testing.T) {
	var pngData, jpegData bytes.Buffer
	img := image.NewRGBA(image.Rect(0, 0, 8, 8))
	if err := png.Encode(&pngData, img); err != nil {
		t.Fatal(err)
	}
	if err := jpeg.Encode(&jpegData, img, nil); err != nil {
		t.Fatal(err)
	}
	dir := t.TempDir()
	// 扩展名与内容不同，确保根据实际图片内容设置 MIME。
	inputs := []struct {
		field, name, contentType string
		data                     []byte
	}{
		{"image", "reference.bin", "image/png", pngData.Bytes()},
		{"image", "photo.png", "image/jpeg", jpegData.Bytes()},
		{"mask", "mask.png", "image/png", pngData.Bytes()},
	}
	for _, input := range inputs {
		if err := os.WriteFile(filepath.Join(dir, input.name), input.data, 0600); err != nil {
			t.Fatal(err)
		}
	}
	for _, model := range []string{"gpt-image-2", "gpt-image-2.5", "gpt-image-2.5-flare", "gpt-image-2.5-sunburst"} {
		t.Run(model, func(t *testing.T) {
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.Method != http.MethodPost || r.URL.Path != "/v1/images/edits" {
					t.Errorf("错误接口：%s %s", r.Method, r.URL.Path)
				}
				if r.Header.Get("Authorization") != "Bearer test-key" {
					t.Error("缺少认证头")
				}
				if err := r.ParseMultipartForm(1 << 20); err != nil {
					t.Error(err)
					http.Error(w, "invalid multipart", 400)
					return
				}
				defer r.MultipartForm.RemoveAll()
				for key, want := range map[string]string{"model": model, "prompt": "Change only the mug color", "size": "1024x1024", "quality": "auto"} {
					if got := r.FormValue(key); got != want {
						t.Errorf("%s = %q，期望 %q", key, got, want)
					}
				}
				if len(r.MultipartForm.File["image"]) != 2 || len(r.MultipartForm.File["mask"]) != 1 {
					t.Error("参考图或蒙版数量错误")
					http.Error(w, "missing files", 400)
					return
				}
				for i, input := range inputs {
					index := i
					if input.field == "mask" {
						index = 0
					}
					header := r.MultipartForm.File[input.field][index]
					if header.Header.Get("Content-Type") != input.contentType {
						t.Errorf("%s MIME = %q，期望 %q", input.name, header.Header.Get("Content-Type"), input.contentType)
						http.Error(w, "unsupported image MIME", 400)
						return
					}
					if header.Filename != input.name {
						t.Errorf("文件名 = %q，期望 %q", header.Filename, input.name)
					}
					file, err := header.Open()
					if err != nil {
						t.Error(err)
						return
					}
					data, err := io.ReadAll(file)
					file.Close()
					if err != nil || !bytes.Equal(data, input.data) {
						t.Errorf("%s 上传内容不完整：%v", input.name, err)
					}
				}
				w.Header().Set("Content-Type", "application/json")
				json.NewEncoder(w).Encode(map[string]any{"data": []map[string]string{{"b64_json": base64.StdEncoding.EncodeToString(pngData.Bytes())}}})
			}))
			defer server.Close()
			t.Setenv("CODEX_API_URL", server.URL)
			t.Setenv("CODEX_API_KEY", "test-key")
			out := filepath.Join(dir, model+"-edited.png")
			_, err := edit("Change only the mug color", []string{filepath.Join(dir, inputs[0].name), filepath.Join(dir, inputs[1].name)}, filepath.Join(dir, inputs[2].name), out,
				commonArgs{model: model, size: "1K", quality: "auto", n: 1, maxAttempts: 1, timeout: 5 * time.Second})
			if err != nil {
				t.Fatal(err)
			}
			data, err := os.ReadFile(out)
			if err != nil || !bytes.Equal(data, pngData.Bytes()) {
				t.Fatalf("编辑结果保存错误：%v", err)
			}
		})
	}
}
