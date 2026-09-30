// Command protogen compiles .proto files with bufbuild/protocompile (pure Go, pinned in go.mod) and
// runs protoc plugins on them — protoc's job, without needing a system protoc.
//
//	protogen -I proto -out gen/proto -plugin protoc-gen-go=/path -plugin protoc-gen-go-grpc=/path \
//	    -opt paths=source_relative yourapp/v1/a.proto yourapp/v1/b.proto
package main

import (
	"bytes"
	"context"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/bufbuild/protocompile"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/reflect/protodesc"
	"google.golang.org/protobuf/reflect/protoreflect"
	"google.golang.org/protobuf/types/descriptorpb"
	"google.golang.org/protobuf/types/pluginpb"
)

type multi []string

func (m *multi) String() string     { return strings.Join(*m, ",") }
func (m *multi) Set(v string) error { *m = append(*m, v); return nil }

func main() {
	var include, out, opt string
	var plugins multi
	flag.StringVar(&include, "I", ".", "import path")
	flag.StringVar(&out, "out", ".", "output directory")
	flag.StringVar(&opt, "opt", "", "plugin parameter")
	flag.Var(&plugins, "plugin", "name=path of a protoc plugin (repeatable)")
	flag.Parse()
	if err := run(include, out, opt, plugins, flag.Args()); err != nil {
		fmt.Fprintln(os.Stderr, "protogen:", err)
		os.Exit(1)
	}
}

func run(include, out, opt string, plugins, files []string) error {
	compiler := protocompile.Compiler{
		Resolver: protocompile.WithStandardImports(&protocompile.SourceResolver{ImportPaths: []string{include}}),
	}
	compiled, err := compiler.Compile(context.Background(), files...)
	if err != nil {
		return err
	}
	// The request carries every file the targets depend on, dependencies first.
	var protos []*descriptorpb.FileDescriptorProto
	seen := map[string]bool{}
	var add func(fd protoreflect.FileDescriptor)
	add = func(fd protoreflect.FileDescriptor) {
		if seen[fd.Path()] {
			return
		}
		seen[fd.Path()] = true
		imports := fd.Imports()
		for i := 0; i < imports.Len(); i++ {
			add(imports.Get(i).FileDescriptor)
		}
		protos = append(protos, protodesc.ToFileDescriptorProto(fd))
	}
	for _, f := range compiled {
		add(f)
	}
	req := &pluginpb.CodeGeneratorRequest{FileToGenerate: files, ProtoFile: protos}
	if opt != "" {
		req.Parameter = proto.String(opt)
	}
	in, err := proto.Marshal(req)
	if err != nil {
		return err
	}
	for _, p := range plugins {
		name, path, ok := strings.Cut(p, "=")
		if !ok {
			return fmt.Errorf("-plugin %q: want name=path", p)
		}
		cmd := exec.Command(path)
		cmd.Stdin = bytes.NewReader(in)
		cmd.Stderr = os.Stderr
		raw, err := cmd.Output()
		if err != nil {
			return fmt.Errorf("%s: %w", name, err)
		}
		var resp pluginpb.CodeGeneratorResponse
		if err := proto.Unmarshal(raw, &resp); err != nil {
			return fmt.Errorf("%s: bad response: %w", name, err)
		}
		if resp.Error != nil {
			return fmt.Errorf("%s: %s", name, resp.GetError())
		}
		for _, f := range resp.File {
			dst := filepath.Join(out, f.GetName())
			if err := os.MkdirAll(filepath.Dir(dst), 0o755); err != nil {
				return err
			}
			if err := os.WriteFile(dst, []byte(f.GetContent()), 0o644); err != nil {
				return err
			}
		}
	}
	return nil
}
