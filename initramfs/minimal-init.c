/*
 * initramfs/minimal-init.c -- init estatico do "boot minimo" do topaz/tapas.
 *
 * Substitui a ramdisk generica do Android (que tenta montar /system e falha
 * porque a base 6.12 nao tem o parser de particoes dinamicas, msm_partition).
 * O objetivo e o kernel 6.12 subir com console serial utilizavel e um shell
 * simples, sem depender de nenhum driver vendor.
 *
 * Compilacao (aarch64, estatico):
 *   aarch64-linux-gnu-gcc -static -O2 -o init minimal-init.c
 *
 * Comportamento:
 *   1. redireciona stdin/stdout/stderr para /dev/console;
 *   2. monta /proc, /sys, /dev (devtmpfs) e /tmp (tmpfs);
 *   3. imprime um banner com versao do kernel, cmdline e modelo do DT;
 *   4. executa /bin/sh (busybox), se existir;
 *   5. sem shell: imprime o estado e dorme, para o kernel nao entrar em panic
 *      de "Attempted to kill init".
 */

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>

static void mount_fs(const char *source, const char *target, const char *type,
		     unsigned long flags)
{
	struct stat st;

	if (stat(target, &st) != 0) {
		if (mkdir(target, 0755) != 0 && errno != EEXIST) {
			fprintf(stderr, "[init-min] mkdir %s: %s\n", target,
				strerror(errno));
			return;
		}
	}
	if (mount(source, target, type, flags, NULL) != 0)
		fprintf(stderr, "[init-min] mount %s (%s): %s\n", target, type,
			strerror(errno));
	else
		fprintf(stderr, "[init-min] mount %s ok\n", target);
}

static void setup_console(void)
{
	int fd = open("/dev/console", O_RDWR);

	if (fd < 0)
		return;
	dup2(fd, STDIN_FILENO);
	dup2(fd, STDOUT_FILENO);
	dup2(fd, STDERR_FILENO);
	if (fd > STDERR_FILENO)
		close(fd);
}

static void dump_file(const char *path, const char *label)
{
	char buffer[512];
	FILE *file = fopen(path, "r");
	size_t got;

	if (!file)
		return;
	got = fread(buffer, 1, sizeof(buffer) - 1, file);
	if (got > 0) {
		buffer[got] = '\0';
		fprintf(stderr, "[init-min] %s: %s\n", label, buffer);
	}
	fclose(file);
}

static int run_shell(void)
{
	pid_t pid = fork();

	if (pid < 0)
		return -1;
	if (pid == 0) {
		execl("/bin/sh", "sh", (char *)NULL);
		execl("/bin/busybox", "busybox", "sh", (char *)NULL);
		_exit(127);
	}
	for (;;) {
		int status = 0;
		pid_t done = waitpid(pid, &status, 0);

		if (done < 0) {
			if (errno == EINTR)
				continue;
			return -1;
		}
		if (WIFEXITED(status) || WIFSIGNALED(status))
			return status;
	}
}

int main(void)
{
	setup_console();

	fprintf(stderr, "\n[init-min] boot minimo do port GKI 6.12 (topaz/tapas)\n");

	mount_fs("proc", "/proc", "proc", 0);
	mount_fs("sysfs", "/sys", "sysfs", 0);
	mount_fs("devtmpfs", "/dev", "devtmpfs", 0);
	mount_fs("tmpfs", "/tmp", "tmpfs", 0);

	dump_file("/proc/version", "kernel");
	dump_file("/proc/cmdline", "cmdline");
	dump_file("/proc/device-tree/model", "model");

	fprintf(stderr, "[init-min] montagens:\n");
	mount_fs("debugfs", "/sys/kernel/debug", "debugfs", 0);
	mount_fs("tracefs", "/sys/kernel/tracing", "tracefs", 0);

	if (access("/bin/sh", X_OK) == 0) {
		fprintf(stderr, "[init-min] iniciando /bin/sh (digite help)\n");
		run_shell();
		fprintf(stderr, "[init-min] o shell terminou; reiniciando o init\n");
	} else {
		fprintf(stderr, "[init-min] /bin/sh ausente: sem shell, "
				"o kernel fica vivo apenas com o console\n");
	}

	for (;;)
		pause();
	return 0;
}
