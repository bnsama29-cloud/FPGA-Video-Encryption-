// Minimal stand-in for Vitis HLS <hls_stream.h> so the C testbench can be
// compiled with plain g++ (make hls-csim) without Vitis installed.
// Vitis HLS uses its own header; this directory is NOT added there.
#pragma once
#include <cstddef>
#include <queue>
#include <stdexcept>

namespace hls {
template <typename T>
class stream {
    std::queue<T> q_;
public:
    stream() {}
    explicit stream(const char *) {}
    void write(const T &v) { q_.push(v); }
    T read() {
        if (q_.empty()) throw std::runtime_error("read from empty hls::stream (testbench fed too few values?)");
        T v = q_.front(); q_.pop(); return v;
    }
    bool empty() const { return q_.empty(); }
    bool full() const { return false; }
    std::size_t size() const { return q_.size(); }
    stream &operator<<(const T &v) { write(v); return *this; }
    stream &operator>>(T &v) { v = read(); return *this; }
};
}  // namespace hls
