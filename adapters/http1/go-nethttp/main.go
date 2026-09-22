// Reads hex-encoded chunked-body byte strings on stdin, one per line.
// Wraps each in a minimal POST request with Transfer-Encoding: chunked,
// parses via http.ReadRequest + server-layer header validation, drains
// the body, and writes {"accept": bool, "body_hex": ..., "consumed": N}.
package main

import (
	"bufio"
	"bytes"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"

	"golang.org/x/net/http/httpguts"
)

var reqHead = []byte("POST / HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\n\r\n")

type verdict struct {
	Accept   bool    `json:"accept"`
	BodyHex  *string `json:"body_hex,omitempty"`
	Consumed *int    `json:"consumed,omitempty"`
	Error    string  `json:"error,omitempty"`
}

func feed(buf []byte) verdict {
	total := append(append([]byte{}, reqHead...), buf...)
	rd := bytes.NewReader(total)
	br := bufio.NewReader(rd)
	req, err := http.ReadRequest(br)
	if err != nil {
		return verdict{Accept: false, Error: err.Error()}
	}
	for k, vv := range req.Header {
		if !httpguts.ValidHeaderFieldName(k) {
			return verdict{Accept: false, Error: "invalid header name"}
		}
		for _, v := range vv {
			if !httpguts.ValidHeaderFieldValue(v) {
				return verdict{Accept: false, Error: "invalid header value"}
			}
		}
	}
	body, err := io.ReadAll(req.Body)
	req.Body.Close()
	if err != nil {
		return verdict{Accept: false, Error: err.Error()}
	}
	consumed := len(buf) - br.Buffered() - rd.Len()
	bh := hex.EncodeToString(body)
	return verdict{Accept: true, BodyHex: &bh, Consumed: &consumed}
}

func main() {
	sc := bufio.NewScanner(os.Stdin)
	sc.Buffer(make([]byte, 0, 1<<20), 1<<20)
	out := bufio.NewWriter(os.Stdout)
	defer out.Flush()
	for sc.Scan() {
		buf, err := hex.DecodeString(sc.Text())
		var v verdict
		if err != nil {
			v = verdict{Accept: false, Error: "bad-hex"}
		} else {
			v = feed(buf)
		}
		b, _ := json.Marshal(v)
		fmt.Fprintln(out, string(b))
		out.Flush()
	}
	if err := sc.Err(); err != nil {
		fmt.Fprintln(os.Stderr, "scan:", err)
		os.Exit(1)
	}
}
