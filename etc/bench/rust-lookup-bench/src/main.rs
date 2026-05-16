use fst::Set;
use packageurl::PackageUrl;
use std::env;
use std::fs;
use std::process;
use std::str::FromStr;
use std::time::Instant;

fn run() -> Result<(), Box<dyn std::error::Error>> {
    let args = env::args().collect::<Vec<_>>();
    if args.len() != 3 {
        return Err(format!("usage: {} <fst-path> <queries-path>", args[0]).into());
    }

    let fst_data = fs::read(&args[1])?;
    let set = Set::new(fst_data.as_slice())?;
    let queries = fs::read_to_string(&args[2])?;

    let start = Instant::now();
    let mut hits = 0usize;
    for query in queries.lines() {
        let purl = PackageUrl::from_str(query)?;
        if purl.version().is_some() || !purl.qualifiers().is_empty() || purl.subpath().is_some() {
            return Err("only base PURL is supported".into());
        }

        let key = query.trim_end_matches('/');
        if set.contains(key) {
            hits += 1;
        }
    }

    println!("hits={hits}");
    println!("lookup_seconds={:.6}", start.elapsed().as_secs_f64());
    Ok(())
}

fn main() {
    if let Err(error) = run() {
        eprintln!("{error}");
        process::exit(1);
    }
}
