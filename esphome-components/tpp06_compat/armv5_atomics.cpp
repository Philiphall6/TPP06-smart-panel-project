#include <pthread.h>
#include <stdint.h>

#if defined(USE_HOST) && defined(__arm__) && defined(TPP06_ZIG_TOOLCHAIN)

// ARMv5 has no load-linked/store-conditional instruction. GCC's uClibc
// toolchain supplies these helpers itself, while Zig's musl toolchain expects
// the application to provide them. A process-wide lock is sufficient for the
// small number of ESPHome atomics and also works on the TPP06 Linux 4.4 kernel.
namespace {
pthread_mutex_t atomic_lock = PTHREAD_MUTEX_INITIALIZER;

class AtomicGuard {
 public:
  AtomicGuard() { pthread_mutex_lock(&atomic_lock); }
  ~AtomicGuard() { pthread_mutex_unlock(&atomic_lock); }
};
}  // namespace

#define ASM_NAME(name) __asm__(name)
#define DEFINE_SYNC_HELPERS(SUFFIX, TYPE, UTYPE)                                    \
  extern "C" TYPE tpp06_cas_##SUFFIX(volatile TYPE *, TYPE, TYPE, ...) noexcept ASM_NAME("__sync_val_compare_and_swap_" #SUFFIX); \
  extern "C" TYPE tpp06_cas_##SUFFIX(volatile TYPE *ptr, TYPE old_value, TYPE new_value, ...) noexcept { \
    AtomicGuard guard;                                                               \
    TYPE previous = *ptr;                                                            \
    if (previous == old_value)                                                       \
      *ptr = new_value;                                                              \
    return previous;                                                                 \
  }                                                                                  \
  extern "C" TYPE tpp06_test_set_##SUFFIX(volatile TYPE *, TYPE, ...) noexcept ASM_NAME("__sync_lock_test_and_set_" #SUFFIX); \
  extern "C" TYPE tpp06_test_set_##SUFFIX(volatile TYPE *ptr, TYPE value, ...) noexcept { \
    AtomicGuard guard;                                                               \
    TYPE previous = *ptr;                                                            \
    *ptr = value;                                                                    \
    return previous;                                                                 \
  }                                                                                  \
  extern "C" TYPE tpp06_add_##SUFFIX(volatile TYPE *, TYPE, ...) noexcept ASM_NAME("__sync_fetch_and_add_" #SUFFIX); \
  extern "C" TYPE tpp06_add_##SUFFIX(volatile TYPE *ptr, TYPE value, ...) noexcept { \
    AtomicGuard guard; TYPE previous = *ptr; *ptr = previous + value; return previous; \
  }                                                                                  \
  extern "C" TYPE tpp06_sub_##SUFFIX(volatile TYPE *, TYPE, ...) noexcept ASM_NAME("__sync_fetch_and_sub_" #SUFFIX); \
  extern "C" TYPE tpp06_sub_##SUFFIX(volatile TYPE *ptr, TYPE value, ...) noexcept { \
    AtomicGuard guard; TYPE previous = *ptr; *ptr = previous - value; return previous; \
  }                                                                                  \
  extern "C" TYPE tpp06_and_##SUFFIX(volatile TYPE *, TYPE, ...) noexcept ASM_NAME("__sync_fetch_and_and_" #SUFFIX); \
  extern "C" TYPE tpp06_and_##SUFFIX(volatile TYPE *ptr, TYPE value, ...) noexcept { \
    AtomicGuard guard; TYPE previous = *ptr; *ptr = previous & value; return previous; \
  }                                                                                  \
  extern "C" TYPE tpp06_or_##SUFFIX(volatile TYPE *, TYPE, ...) noexcept ASM_NAME("__sync_fetch_and_or_" #SUFFIX); \
  extern "C" TYPE tpp06_or_##SUFFIX(volatile TYPE *ptr, TYPE value, ...) noexcept { \
    AtomicGuard guard; TYPE previous = *ptr; *ptr = previous | value; return previous; \
  }                                                                                  \
  extern "C" TYPE tpp06_xor_##SUFFIX(volatile TYPE *, TYPE, ...) noexcept ASM_NAME("__sync_fetch_and_xor_" #SUFFIX); \
  extern "C" TYPE tpp06_xor_##SUFFIX(volatile TYPE *ptr, TYPE value, ...) noexcept { \
    AtomicGuard guard; TYPE previous = *ptr; *ptr = previous ^ value; return previous; \
  }                                                                                  \
  extern "C" TYPE tpp06_nand_##SUFFIX(volatile TYPE *, TYPE, ...) noexcept ASM_NAME("__sync_fetch_and_nand_" #SUFFIX); \
  extern "C" TYPE tpp06_nand_##SUFFIX(volatile TYPE *ptr, TYPE value, ...) noexcept { \
    AtomicGuard guard; TYPE previous = *ptr; *ptr = ~(previous & value); return previous; \
  }                                                                                  \
  extern "C" TYPE tpp06_umin_##SUFFIX(volatile TYPE *, TYPE, ...) noexcept ASM_NAME("__sync_fetch_and_umin_" #SUFFIX); \
  extern "C" TYPE tpp06_umin_##SUFFIX(volatile TYPE *ptr, TYPE value, ...) noexcept { \
    AtomicGuard guard; TYPE previous = *ptr; if (static_cast<UTYPE>(value) < static_cast<UTYPE>(previous)) *ptr = value; return previous; \
  }                                                                                  \
  extern "C" TYPE tpp06_umax_##SUFFIX(volatile TYPE *, TYPE, ...) noexcept ASM_NAME("__sync_fetch_and_umax_" #SUFFIX); \
  extern "C" TYPE tpp06_umax_##SUFFIX(volatile TYPE *ptr, TYPE value, ...) noexcept { \
    AtomicGuard guard; TYPE previous = *ptr; if (static_cast<UTYPE>(value) > static_cast<UTYPE>(previous)) *ptr = value; return previous; \
  }

DEFINE_SYNC_HELPERS(1, char, uint8_t)
DEFINE_SYNC_HELPERS(2, short, uint16_t)
DEFINE_SYNC_HELPERS(4, int, uint32_t)

#endif
