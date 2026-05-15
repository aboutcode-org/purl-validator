use std::fs;
use std::fs::File;
use std::io::{BufRead, BufReader, BufWriter};
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant};


use dawg::Dawg;
use fst::raw::Fst;
use fst::SetBuilder;

// Simple benchmark to compare PURL lookup using a DAWG or an FST

const N_LOOKUPS: usize = 1_000_000;
const OUT_DIR: &str = "target/purl-bench";
const PURL_DATA_DIR: &str = "purl-validator.rs/fst_builder/data";

struct BenchResult {
    name: &'static str,
    build_time: Duration,
    disk_bytes: u64,
    lookup_time: Duration,
    hits: usize,
}

/// Collect all PURL files (each with one PURL per lien)
fn purl_files(path: &Path) -> Result<Vec<PathBuf>, Box<dyn std::error::Error>> {
    let mut files = fs::read_dir(path)?
        .map(|entry| entry.map(|entry| entry.path()))
        .collect::<Result<Vec<_>, _>>()?;
    files.retain(|path| path.extension().and_then(|ext| ext.to_str()) == Some("txt"));
    files.sort();
    Ok(files)
}

fn load_purls(path: &Path) -> Result<(Vec<String>, usize), Box<dyn std::error::Error>> {
    let mut keys = Vec::new();
    let mut raw_count = 0;
    for file_path in purl_files(path)? {
        let file = File::open(&file_path)?;
        let reader = BufReader::new(file);
        for line in reader.lines() {
            let line = line?;
            if line.is_empty() {
                continue;
            }
            raw_count += 1;
            keys.push(line);
        }
    }
    keys.sort();
    Ok((keys, raw_count))
}

fn build_queries(keys: &[String]) -> Vec<String> {
    let mut queries = Vec::with_capacity(N_LOOKUPS);
    let half = N_LOOKUPS / 2;
    let n_keys = keys.len();
    for i in 0..half {
        queries.push(keys[(i * 9_973) % n_keys].clone());
        queries.push(format!("{}-missing-{}", keys[(i * 15_485_863) % n_keys], i));
    }
    queries
}

/// Bench for the fst crate
fn bench_fst(keys: &[String], queries: &[String]) -> Result<BenchResult, Box<dyn std::error::Error>> {
    let path = Path::new(OUT_DIR).join("real-purls.fst");

    let build_start = Instant::now();
    {
        let file = File::create(&path)?;
        let mut builder = SetBuilder::new(file)?;
        for key in keys {
            builder.insert(key)?;
        }
        builder.finish()?;
    }
    let build_time = build_start.elapsed();
    let disk_bytes = fs::metadata(&path)?.len();

    let bytes = fs::read(&path)?;
    let fst = Fst::new(bytes)?;
    let lookup_start = Instant::now();
    let hits = queries
        .iter()
        .filter(|query| fst.get(query.as_bytes()).is_some())
        .count();
    let lookup_time = lookup_start.elapsed();

    Ok(BenchResult {
        name: "fst::Set",
        build_time,
        disk_bytes,
        lookup_time,
        hits,
    })
}

/// Bench for the dwag crate
fn bench_dawg_crate(
    keys: &[String],
    queries: &[String],
) -> Result<BenchResult, Box<dyn std::error::Error>> {
    let path = Path::new(OUT_DIR).join("real-purls.dawg-bincode");

    let build_start = Instant::now();
    let mut dawg = Dawg::new();
    for key in keys {
        dawg.insert(key.clone());
    }
    dawg.finish();
    let build_time = build_start.elapsed();

    {
        let file = File::create(&path)?;
        let mut writer = BufWriter::new(file);
        bincode::serialize_into(&mut writer, &dawg)?;
    }
    let disk_bytes = fs::metadata(&path)?.len();

    let lookup_start = Instant::now();
    let hits = queries
        .iter()
        .filter(|query| dawg.is_word(query.as_str(), true).is_some())
        .count();
    let lookup_time = lookup_start.elapsed();

    Ok(BenchResult {
        name: "dawg::Dawg",
        build_time,
        disk_bytes,
        lookup_time,
        hits,
    })
}

fn print_measurement(measurement: &BenchResult) {
    println!(
        "| {} | {:.3} | {} | {:.3} | {} |",
        measurement.name,
        measurement.build_time.as_secs_f64(),
        measurement.disk_bytes,
        measurement.lookup_time.as_secs_f64(),
        measurement.hits,
    );
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    fs::create_dir_all(OUT_DIR)?;

    println!("Loading PURLs from {PURL_DATA_DIR}");
    let load_start = Instant::now();
    let (keys, raw_count) = load_purls(Path::new(PURL_DATA_DIR))?;
    let load_time = load_start.elapsed();
    let queries = build_queries(&keys);
    println!("Unique sorted keys: {}", keys.len());
    println!("Input load/sort seconds: {:.3}", load_time.as_secs_f64());
    println!("Lookup queries: {N_LOOKUPS}");
    println!("Expected hits: {}", N_LOOKUPS / 2);
    println!();
    println!("| structure | build seconds | disk bytes | lookup seconds | hits |");
    println!("| --- | ---: | ---: | ---: | ---: |");

    let fst = bench_fst(&keys, &queries)?;
    print_measurement(&fst);

    let dawg = bench_dawg_crate(&keys, &queries)?;
    print_measurement(&dawg);

    Ok(())
}
