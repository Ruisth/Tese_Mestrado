for i in 01 02 03; do run_test itest-smoke-$i-q1 42 --scenario smoke || { stop "test 1 interrupted at itest-smoke-$i-q1 - the remaining repetitions were NOT started"; break; }; done
