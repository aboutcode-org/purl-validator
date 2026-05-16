use std::fs;
use std::fs::File;
use std::io::{BufRead, BufReader, BufWriter};
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant};

use dawg::Dawg;
use fst::SetBuilder;
use fst::raw::Fst;

// Simple benchmark to compare PURL lookup using a DAWG or an FST

const N_LOOKUPS: usize = 1_000_000;

struct BenchResult {
    name: &'static str,
    build_time: Duration,
    disk_bytes: u64,
    lookup_time: Duration,
    hits: usize,
}

/// Collect all PURL files, one PURL per line.
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
    keys.dedup();
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
fn bench_fst(
    keys: &[String],
    queries: &[String],
    out_dir: &Path,
) -> Result<BenchResult, Box<dyn std::error::Error>> {
    let path = out_dir.join("real-purls.fst");

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
    out_dir: &Path,
) -> Result<BenchResult, Box<dyn std::error::Error>> {
    let path = out_dir.join("real-purls.dawg-bincode");

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
        "{:<20}   {:>12.6}   {:>14.6}   {:<27}",
        measurement.name,
        measurement.build_time.as_secs_f64(),
        measurement.lookup_time.as_secs_f64(),
        storage_size(measurement.disk_bytes),
    );
}

fn storage_size(bytes: u64) -> String {
    let mib = (bytes as f64 / 1024.0 / 1024.0).round() as u64;
    format!("{mib}MB")
}

fn default_data_dir() -> PathBuf {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    manifest_dir
        .ancestors()
        .nth(4)
        .expect("cannot find workspace directory")
        .join("purl-validator.rs/fst_builder/data")
}

fn default_out_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("target/purl-bench")
}

fn parse_args() -> Result<(PathBuf, PathBuf), Box<dyn std::error::Error>> {
    let mut data_dir = default_data_dir();
    let mut out_dir = default_out_dir();
    let mut args = std::env::args().skip(1);

    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--data-dir" => {
                data_dir = PathBuf::from(args.next().ok_or("--data-dir requires a value")?);
            }
            "--out-dir" => {
                out_dir = PathBuf::from(args.next().ok_or("--out-dir requires a value")?);
            }
            "--help" | "-h" => {
                println!("usage: rust-fst-dawg-bench [--data-dir PATH] [--out-dir PATH]");
                std::process::exit(0);
            }
            _ => return Err(format!("unknown argument: {arg}").into()),
        }
    }

    Ok((data_dir, out_dir))
}

fn check_hits(measurement: &BenchResult) -> Result<(), Box<dyn std::error::Error>> {
    let expected_hits = N_LOOKUPS / 2;
    if measurement.hits != expected_hits {
        return Err(format!(
            "{} returned {} hits; expected {}",
            measurement.name, measurement.hits, expected_hits
        )
        .into());
    }
    Ok(())
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let (data_dir, out_dir) = parse_args()?;
    fs::create_dir_all(&out_dir)?;

    let load_start = Instant::now();
    let (keys, _raw_count) = load_purls(&data_dir)?;
    if keys.is_empty() {
        return Err(format!("no PURLs in {}", data_dir.display()).into());
    }
    let _load_time = load_start.elapsed();
    let queries = build_queries(&keys);
    println!(
        "{:<20}   {:>12}   {:>14}   {:<27}",
        "structure", "build (secs)", "lookup (secs)", "storage size"
    );
    println!(
        "{:<20}   {:>12}   {:>14}   {:<27}",
        "-".repeat(20),
        "-".repeat(12),
        "-".repeat(14),
        "-".repeat(27)
    );

    let fst = bench_fst(&keys, &queries, &out_dir)?;
    check_hits(&fst)?;
    print_measurement(&fst);

    let dawg = bench_dawg_crate(&keys, &queries, &out_dir)?;
    check_hits(&dawg)?;
    print_measurement(&dawg);

    Ok(())
}
