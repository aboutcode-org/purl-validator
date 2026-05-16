package main

import (
	"bufio"
	"fmt"
	"os"
	"time"

	"github.com/blevesearch/vellum"
	packageurl "github.com/package-url/packageurl-go"
)

func run() error {
	if len(os.Args) != 3 {
		return fmt.Errorf("usage: %s <fst-path> <queries-path>", os.Args[0])
	}

	data, err := os.ReadFile(os.Args[1])
	if err != nil {
		return err
	}
	fstMap, err := vellum.Load(data)
	if err != nil {
		return err
	}

	file, err := os.Open(os.Args[2])
	if err != nil {
		return err
	}
	defer file.Close()

	start := time.Now()
	hits := 0
	scanner := bufio.NewScanner(file)
	scanner.Buffer(make([]byte, 1024), 1024*1024)
	for scanner.Scan() {
		query := scanner.Text()
		instance, err := packageurl.FromString(query)
		if err != nil {
			return err
		}
		if instance.Version != "" || len(instance.Qualifiers) > 0 || instance.Subpath != "" {
			return fmt.Errorf("only base PURL is supported")
		}

		ok, err := fstMap.Contains([]byte(query))
		if err != nil {
			return err
		}
		if ok {
			hits++
		}
	}
	if err := scanner.Err(); err != nil {
		return err
	}

	fmt.Printf("hits=%d\n", hits)
	fmt.Printf("lookup_seconds=%.6f\n", time.Since(start).Seconds())
	return nil
}

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
