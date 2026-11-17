#include <cerrno>
#include <cstdint>
#include <ctime>
#include <sys/select.h>
#include <sys/syscall.h>
#include <unistd.h>

#if defined(USE_HOST) && defined(__arm__) && __SIZEOF_LONG__ == 4

// Zig's musl headers intentionally omit SYS_clock_gettime on 32-bit ARM even
// though the legacy Linux 4.4 syscall is present.  Keep the ABI number local
// to this ARM-only compatibility unit.
#ifndef SYS_clock_gettime
#define SYS_clock_gettime 263
#endif

namespace {

struct KernelTimespec32 {
  int32_t seconds;
  int32_t nanoseconds;
};

struct KernelTimeval32 {
  int32_t seconds;
  int32_t microseconds;
};

}  // namespace

extern "C" int __wrap_clock_gettime(clockid_t clock_id, struct timespec *output) {
  KernelTimespec32 kernel_time{};
  const int result = static_cast<int>(::syscall(SYS_clock_gettime, clock_id, &kernel_time));
  if (result == 0 && output != nullptr) {
    output->tv_sec = kernel_time.seconds;
    output->tv_nsec = kernel_time.nanoseconds;
  }
  return result;
}

extern "C" int __wrap_nanosleep(const struct timespec *request, struct timespec *remaining) {
  if (request == nullptr) {
    errno = EFAULT;
    return -1;
  }
  KernelTimespec32 kernel_request{static_cast<int32_t>(request->tv_sec), static_cast<int32_t>(request->tv_nsec)};
  KernelTimespec32 kernel_remaining{};
  const int result = static_cast<int>(::syscall(SYS_nanosleep, &kernel_request, &kernel_remaining));
  if (result != 0 && remaining != nullptr) {
    remaining->tv_sec = kernel_remaining.seconds;
    remaining->tv_nsec = kernel_remaining.nanoseconds;
  }
  return result;
}

extern "C" int __wrap_select(int count, fd_set *read_fds, fd_set *write_fds, fd_set *except_fds,
                               struct timeval *timeout) {
  if (timeout == nullptr)
    return static_cast<int>(::syscall(SYS__newselect, count, read_fds, write_fds, except_fds, nullptr));

  KernelTimeval32 kernel_timeout{static_cast<int32_t>(timeout->tv_sec), static_cast<int32_t>(timeout->tv_usec)};
  const int result = static_cast<int>(
      ::syscall(SYS__newselect, count, read_fds, write_fds, except_fds, &kernel_timeout));
  timeout->tv_sec = kernel_timeout.seconds;
  timeout->tv_usec = kernel_timeout.microseconds;
  return result;
}

extern "C" time_t __wrap_time(time_t *output) {
  KernelTimespec32 kernel_time{};
  if (::syscall(SYS_clock_gettime, CLOCK_REALTIME, &kernel_time) != 0)
    return static_cast<time_t>(-1);
  const time_t value = static_cast<time_t>(kernel_time.seconds);
  if (output != nullptr)
    *output = value;
  return value;
}

#endif
