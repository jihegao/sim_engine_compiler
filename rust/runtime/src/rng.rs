/// CPython `_random.Random` compatible MT19937 for integer seeds.
#[derive(Clone, Debug)]
pub struct PythonRandom {
    mt: [u32; 624],
    index: usize,
}

impl PythonRandom {
    pub fn from_u64(seed: u64) -> Self {
        let words = if seed == 0 {
            vec![0]
        } else {
            let mut value = seed;
            let mut out = Vec::new();
            while value != 0 {
                out.push(value as u32);
                value >>= 32;
            }
            out
        };
        Self::from_words(&words)
    }

    pub fn from_be_bytes(bytes: &[u8]) -> Self {
        let first = bytes
            .iter()
            .position(|item| *item != 0)
            .unwrap_or(bytes.len());
        let data = &bytes[first..];
        if data.is_empty() {
            return Self::from_words(&[0]);
        }
        let mut words = Vec::new();
        let mut end = data.len();
        while end > 0 {
            let start = end.saturating_sub(4);
            let mut chunk = [0u8; 4];
            chunk[4 - (end - start)..].copy_from_slice(&data[start..end]);
            words.push(u32::from_be_bytes(chunk));
            end = start;
        }
        Self::from_words(&words)
    }

    fn from_words(key: &[u32]) -> Self {
        let mut value = Self {
            mt: [0; 624],
            index: 624,
        };
        value.init_genrand(19_650_218);
        let mut i = 1usize;
        let mut j = 0usize;
        for _ in 0..624.max(key.len()) {
            let previous = value.mt[i - 1];
            value.mt[i] = (value.mt[i] ^ (previous ^ (previous >> 30)).wrapping_mul(1_664_525))
                .wrapping_add(key[j])
                .wrapping_add(j as u32);
            i += 1;
            j += 1;
            if i >= 624 {
                value.mt[0] = value.mt[623];
                i = 1;
            }
            if j >= key.len() {
                j = 0;
            }
        }
        for _ in 0..623 {
            let previous = value.mt[i - 1];
            value.mt[i] = (value.mt[i] ^ (previous ^ (previous >> 30)).wrapping_mul(1_566_083_941))
                .wrapping_sub(i as u32);
            i += 1;
            if i >= 624 {
                value.mt[0] = value.mt[623];
                i = 1;
            }
        }
        value.mt[0] = 0x8000_0000;
        value.index = 624;
        value
    }

    fn init_genrand(&mut self, seed: u32) {
        self.mt[0] = seed;
        for i in 1..624 {
            self.mt[i] = 1_812_433_253u32
                .wrapping_mul(self.mt[i - 1] ^ (self.mt[i - 1] >> 30))
                .wrapping_add(i as u32);
        }
    }

    fn next_u32(&mut self) -> u32 {
        if self.index >= 624 {
            const MATRIX_A: u32 = 0x9908_b0df;
            for kk in 0..227 {
                let y = (self.mt[kk] & 0x8000_0000) | (self.mt[kk + 1] & 0x7fff_ffff);
                self.mt[kk] = self.mt[kk + 397] ^ (y >> 1) ^ if y & 1 != 0 { MATRIX_A } else { 0 };
            }
            for kk in 227..623 {
                let y = (self.mt[kk] & 0x8000_0000) | (self.mt[kk + 1] & 0x7fff_ffff);
                self.mt[kk] = self.mt[kk - 227] ^ (y >> 1) ^ if y & 1 != 0 { MATRIX_A } else { 0 };
            }
            let y = (self.mt[623] & 0x8000_0000) | (self.mt[0] & 0x7fff_ffff);
            self.mt[623] = self.mt[396] ^ (y >> 1) ^ if y & 1 != 0 { MATRIX_A } else { 0 };
            self.index = 0;
        }
        let mut y = self.mt[self.index];
        self.index += 1;
        y ^= y >> 11;
        y ^= (y << 7) & 0x9d2c_5680;
        y ^= (y << 15) & 0xefc6_0000;
        y ^= y >> 18;
        y
    }

    pub fn random(&mut self) -> f64 {
        let a = (self.next_u32() >> 5) as u64;
        let b = (self.next_u32() >> 6) as u64;
        ((a << 26) + b) as f64 / 9_007_199_254_740_992.0
    }

    pub fn expovariate(&mut self, rate: f64) -> f64 {
        -(1.0 - self.random()).ln() / rate
    }
}

#[cfg(test)]
mod tests {
    use super::PythonRandom;

    #[test]
    fn matches_cpython_integer_seed() {
        let expected = [
            0.8444218515250481,
            0.7579544029403025,
            0.420571580830845,
            0.25891675029296335,
            0.5112747213686085,
        ];
        let mut rng = PythonRandom::from_u64(0);
        for item in expected {
            assert_eq!(rng.random(), item);
        }
    }
}
