%define LDAP 2
%define MYSQL 0
%define PCRE 1
%define SASL 2
%define TLS 1
%define POSTDROP_GID 90

# On Redhat 8.0.1 and earlier, LDAP is compiled with SASL V1 and won't work
# if postfix is compiled with SASL V2. So we drop to SASL V1 if LDAP is
# requested but use the preferred SASL V2 if LDAP is not requested.
# Sometime soon LDAP will build agains SASL V2 and this won't be needed.

%if %{LDAP} <= 1 && %{SASL} >= 2
%undefine SASL
%define SASL 1
%endif

# Do we use db3 or db4 ? If we have db4, assume db4, otherwise db3.
%define dbver db4

# If set to 1 if official version, 0 if snapshot
%define official 1 
%define ver 2.0.11
%define releasedate 20020624
%define alternatives 1
%if %{official}
Version: %{ver}
%define ftp_directory official
%else
Version: %{ver}-%{releasedate}
%define ftp_directory experimental
%endif
Release: 5
Epoch: 2

%define tlsno pfixtls-0.8.13-2.0.10-0.9.7b

# Postfix requires one exlusive uid/gid and a 2nd exclusive gid for its own
# use.  Let me know if the second gid collides with another package.
# Be careful: Redhat's 'mail' user & group isn't unique!
%define postfix_uid    89
%define postfix_gid    89
%define maildrop_group postdrop
%define maildrop_gid   %{POSTDROP_GID}
%define docdir %{_docdir}/%{name}-%{version}

Name: postfix
Group: System Environment/Daemons
URL: http://www.postfix.org
License: IBM Public License
PreReq: /sbin/chkconfig, /sbin/service, sh-utils
PreReq: fileutils, textutils,
%if %alternatives
PreReq: /usr/sbin/alternatives
%else
Obsoletes: sendmail exim qmail
%endif
PreReq: %{_sbindir}/groupadd, %{_sbindir}/useradd
Provides: MTA smtpd smtpdaemon /usr/bin/newaliases
Summary: Postfix Mail Transport Agent
Source0: ftp://ftp.porcupine.org/mirrors/postfix-release/%{ftp_directory}/%{name}-%{version}.tar.gz
Source3: postfix-etc-init.d-postfix
Source5: postfix-aliases
Source9: ftp://ftp.aet.tu-cottbus.de/pub/postfix_tls/%{tlsno}.tar.gz
Source11: README-Postfix-SASL-RedHat.txt
# Sources >= 100 are config files
Source100: postfix-sasl.conf
Source101: postfix-pam.conf
Source102: postfix-saslauthd.conf
Patch1: postfix-config.patch
Patch2: postfix-smtp_sasl_proto.c.patch
Patch3: postfix-alternatives.patch

# Optional patches - set the appropriate environment variables to include
#                    them when building the package/spec file

BuildRoot: %{_tmppath}/%{name}-buildroot

# Determine the different packages required for building postfix
BuildRequires: gawk, perl, sed, ed, %{dbver}-devel, pkgconfig

Requires: %{dbver}

%if %{LDAP}
BuildRequires: openldap >= 2.0.27, openldap-devel >= 2.0.27
Requires: openldap >= 2.0.27
%endif

%if %{SASL}
BuildRequires: cyrus-sasl >= 2.1.10, cyrus-sasl-devel >= 2.1.10
Requires: cyrus-sasl  >= 2.1.10
%endif

%if %{PCRE}
Requires: pcre
BuildRequires: pcre, pcre-devel
%endif

%if %{MYSQL}
Requires: mysql, mysqlclient9
BuildRequires: mysql, mysqlclient9, mysql-devel
%endif

%if %{TLS}
Requires: openssl
BuildRequires: openssl-devel >= 0.9.6
%endif

Provides: /usr/sbin/sendmail /usr/bin/mailq /usr/bin/rmail

%description
Postfix is a Mail Transport Agent (MTA), supporting LDAP, SMTP AUTH (SASL),
TLS

%prep
umask 022

%setup -q -a 9
# Apply the TLS patch, must be at first, because the changes of master.cf
%if %{TLS}
patch -p1 <%{tlsno}/pfixtls.diff
%patch1 -p1 -b .config
%else
# Without the TLS patch the context lines in this patch don't match.
# Set fuzz to ignore all context lines, this is a bit dangerous.
patch --fuzz=3 -p1 -b -z .config < %{P:1}
%endif

# Apply obligatory patches
%patch2 -p1 -b .auth
%if %alternatives
%patch3 -p1 -b .alternatives
%endif

# Apply optional patches

%build
umask 022

CCARGS=
AUXLIBS=

%ifarch s390 s390x ppc
CCARGS="${CCARGS} -fsigned-char"
%endif

%if %{LDAP}
  CCARGS="${CCARGS} -DHAS_LDAP"
  AUXLIBS="${AUXLIBS} -L%{_libdir} -lldap -llber"
%endif
%if %{PCRE}
  # -I option required for pcre 3.4 (and later?)
  CCARGS="${CCARGS} -DHAS_PCRE -I/usr/include/pcre"
  AUXLIBS="${AUXLIBS} -lpcre"
%endif
%if %{MYSQL}
  CCARGS="${CCARGS} -DHAS_MYSQL -I/usr/include/mysql"
  AUXLIBS="${AUXLIBS} -L%{_libdir}/mysql -lmysqlclient -lm"
%endif
%if %{SASL}
  %define sasl_lib_dir %{_libdir}/sasl2
  CCARGS="${CCARGS} -DUSE_SASL_AUTH"
  %if %{SASL} <= 1
    %define sasl_lib_dir %{_libdir}/sasl
    AUXLIBS="${AUXLIBS} -L%{sasl_lib_dir} -lsasl"
  %else
    %define sasl_lib_dir %{_libdir}/sasl2
    CCARGS="${CCARGS} -I/usr/include/sasl"
    AUXLIBS="${AUXLIBS} -L%{sasl_lib_dir} -lsasl2"
  %endif
%endif
%if %{TLS}
  if pkg-config openssl ; then
    CCARGS="${CCARGS} -DHAS_SSL `pkg-config --cflags openssl`"
    AUXLIBS="${AUXLIBS} `pkg-config --libs openssl`"
  else
    CCARGS="${CCARGS} -DHAS_SSL -I/usr/include/openssl"
    AUXLIBS="${AUXLIBS} -lssl -lcrypto"
  fi
%endif

export CCARGS AUXLIBS
make -f Makefile.init makefiles

unset CCARGS AUXLIBS
make DEBUG="" OPT="$RPM_OPT_FLAGS"

%install
umask 022
/bin/rm -rf   $RPM_BUILD_ROOT
/bin/mkdir -p $RPM_BUILD_ROOT

# install postfix into $RPM_BUILD_ROOT
sh postfix-install -non-interactive \
       install_root=$RPM_BUILD_ROOT \
       config_directory=%{_sysconfdir}/postfix \
       daemon_directory=%{_libexecdir}/postfix \
       command_directory=%{_sbindir} \
       queue_directory=%{_var}/spool/postfix \
       sendmail_path=%{_sbindir}/sendmail.postfix \
       newaliases_path=%{_bindir}/newaliases.postfix \
       mailq_path=%{_bindir}/mailq.postfix \
       mail_owner=postfix \
       setgid_group=%{maildrop_group} \
       manpage_directory=%{_mandir} \
       sample_directory=%{docdir}/samples \
       readme_directory=%{docdir}/README_FILES || exit 1

# Move around the TLS docs
%if %{TLS}
mkdir -p $RPM_BUILD_ROOT%{docdir}/TLS
cp %{tlsno}/doc/* $RPM_BUILD_ROOT%{docdir}/TLS
for i in ACKNOWLEDGEMENTS CHANGES INSTALL README TODO; do
  cp %{tlsno}/$i $RPM_BUILD_ROOT%{docdir}/TLS
done
%endif

# Change alias_maps and alias_database default directory to %{_sysconfdir}/postfix
bin/postconf -c $RPM_BUILD_ROOT%{_sysconfdir}/postfix -e \
	"alias_maps = hash:%{_sysconfdir}/postfix/aliases" \
	"alias_database = hash:%{_sysconfdir}/postfix/aliases" \
|| exit 1

# This installs into the /etc/rc.d/init.d directory
/bin/mkdir -p $RPM_BUILD_ROOT/etc/rc.d/init.d
install -c %{_sourcedir}/postfix-etc-init.d-postfix \
                  $RPM_BUILD_ROOT/etc/rc.d/init.d/postfix

install -c auxiliary/rmail/rmail $RPM_BUILD_ROOT%{_bindir}/rmail

# copy new aliases files and generate a ghost aliases.db file
cp -f %{_sourcedir}/postfix-aliases $RPM_BUILD_ROOT%{_sysconfdir}/postfix/aliases
chmod 644 $RPM_BUILD_ROOT%{_sysconfdir}/postfix/aliases

touch $RPM_BUILD_ROOT/%{_sysconfdir}/postfix/aliases.db

for i in active bounce corrupt defer deferred flush incoming private saved maildrop public pid; do
    mkdir -p $RPM_BUILD_ROOT%{_var}/spool/postfix/$i
done

# install smtp-sink/smtp-source by hand
for i in smtp-sink smtp-source; do
  install -c -m 755 bin/$i $RPM_BUILD_ROOT%{_sbindir}/
done

# Move stuff around so we don't conflict with sendmail
mv $RPM_BUILD_ROOT%{_bindir}/rmail $RPM_BUILD_ROOT%{_bindir}/rmail.postfix
mv $RPM_BUILD_ROOT%{_mandir}/man1/mailq.1 $RPM_BUILD_ROOT%{_mandir}/man1/mailq.postfix.1
mv $RPM_BUILD_ROOT%{_mandir}/man1/newaliases.1 $RPM_BUILD_ROOT%{_mandir}/man1/newaliases.postfix.1
mv $RPM_BUILD_ROOT%{_mandir}/man5/aliases.5 $RPM_BUILD_ROOT%{_mandir}/man5/aliases.postfix.5

# RPM compresses man pages automatically.
# - Edit postfix-files to reflect this, so post-install won't get confused
#   when called during package installation.
ed $RPM_BUILD_ROOT%{_sysconfdir}/postfix/postfix-files <<EOF || exit 1
%s/\(\/man[158]\/.*\.[158]\):/\1.gz:/
w
q
EOF

# Install the smtpd.conf file for SASL support.
mkdir -p $RPM_BUILD_ROOT%{sasl_lib_dir}
install -m 644 %SOURCE100 $RPM_BUILD_ROOT%{sasl_lib_dir}/smtpd.conf
mkdir -p $RPM_BUILD_ROOT%{_sysconfdir}/pam.d
install -m 644 %SOURCE101 $RPM_BUILD_ROOT%{_sysconfdir}/pam.d/smtp.postfix
mkdir -p $RPM_BUILD_ROOT%{_sysconfdir}/sysconfig
install -m 644 %SOURCE102 $RPM_BUILD_ROOT%{_sysconfdir}/sysconfig/saslauthd

# Install Postfix Red Hat HOWTO.
mkdir -p $RPM_BUILD_ROOT%{docdir}
install -c %{SOURCE11} $RPM_BUILD_ROOT%{docdir}

# remove LICENSE file from /etc/postfix (it's still in docdir)
rm -f $RPM_BUILD_ROOT%{_sysconfdir}/postfix/LICENSE
ed $RPM_BUILD_ROOT%{_sysconfdir}/postfix/postfix-files <<EOF || exit 1
g/LICENSE/d
w
q
EOF

# fix path to perl
perl -pi -e "s,/usr/local/bin/perl,/usr/bin/perl,g" html/TLS/loadCAcert.pl

%post
umask 022

/sbin/chkconfig --add postfix

# upgrade configuration files if necessary
sh %{_sysconfdir}/postfix/post-install \
	config_directory=%{_sysconfdir}/postfix \
	daemon_directory=%{_libexecdir}/postfix \
	command_directory=%{_sbindir} \
	mail_owner=postfix \
	setgid_group=%{maildrop_group} \
	manpage_directory=%{_mandir} \
	sample_directory=%{docdir}/samples \
	readme_directory=%{docdir}/README_FILES \
	upgrade-package

%if %alternatives
/usr/sbin/alternatives --install %{_sbindir}/sendmail mta %{_sbindir}/sendmail.postfix 30 \
        --slave %{_bindir}/mailq mta-mailq %{_bindir}/mailq.postfix \
        --slave %{_bindir}/newaliases mta-newaliases %{_bindir}/newaliases.postfix \
        --slave %{_sysconfdir}/pam.d/smtp mta-pam %{_sysconfdir}/pam.d/smtp.postfix \
        --slave %{_bindir}/rmail mta-rmail %{_bindir}/rmail.postfix \
        --slave %{_mandir}/man1/mailq.1.gz mta-mailqman %{_mandir}/man1/mailq.postfix.1.gz \
        --slave %{_mandir}/man1/newaliases.1.gz mta-newaliasesman %{_mandir}/man1/newaliases.postfix.1.gz \
        --slave %{_mandir}/man5/aliases.5.gz mta-aliasesman %{_mandir}/man5/aliases.postfix.5.gz \
	--initscript postfix
%endif

%pre
# Add user and groups if necessary
%{_sbindir}/groupadd -g %{maildrop_gid} -r %{maildrop_group} 2>/dev/null
%{_sbindir}/groupadd -g %{postfix_gid} -r postfix 2>/dev/null
%{_sbindir}/groupadd -g 12 -r mail 2>/dev/null
%{_sbindir}/useradd -d %{_var}/spool/postfix -s /sbin/nologin -g postfix -G mail -M -r -u %{postfix_uid} postfix 2>/dev/null
exit 0

%preun
umask 022

if [ "$1" = 0 ]; then
    # stop postfix silently, but only if it's running
    /sbin/service postfix stop &>/dev/null
    /sbin/chkconfig --del postfix
%if %alternatives
    /usr/sbin/alternatives --remove mta %{_sbindir}/sendmail.postfix
%endif

fi

exit 0

%postun
if [ "$1" != 0 ]; then
	/sbin/service postfix condrestart 2>&1 > /dev/null
fi
exit 0

%clean
/bin/rm -rf $RPM_BUILD_ROOT


%files
%defattr(-, root, root)

%config(noreplace) %{sasl_lib_dir}/smtpd.conf
%config(noreplace) %{_sysconfdir}/pam.d/smtp.postfix
%config(noreplace) %{_sysconfdir}/sysconfig/saslauthd

%verify(not md5 size mtime) %config %dir %{_sysconfdir}/postfix
%attr(0755, root, root) %config %{_sysconfdir}/postfix/postfix-script
%attr(0755, root, root) %config %{_sysconfdir}/postfix/post-install
%attr(0644, root, root)                                                %{_sysconfdir}/postfix/postfix-files
%attr(0644, root, root) %verify(not md5 size mtime) %config(noreplace) %{_sysconfdir}/postfix/main.cf
%attr(0644, root, root)                                                %{_sysconfdir}/postfix/main.cf.default
%attr(0644, root, root) %verify(not md5 size mtime) %config(noreplace) %{_sysconfdir}/postfix/master.cf
%attr(0644, root, root) %verify(not md5 size mtime) %config(noreplace) %{_sysconfdir}/postfix/access
%attr(0644, root, root) %verify(not md5 size mtime) %config(noreplace) %{_sysconfdir}/postfix/aliases
%attr(0644, root, root) %verify(not md5 size mtime) %config(noreplace) %{_sysconfdir}/postfix/aliases.db
%attr(0644, root, root) %verify(not md5 size mtime) %config(noreplace) %{_sysconfdir}/postfix/canonical
%attr(0644, root, root) %verify(not md5 size mtime) %config(noreplace) %{_sysconfdir}/postfix/pcre_table
%attr(0644, root, root) %verify(not md5 size mtime) %config(noreplace) %{_sysconfdir}/postfix/regexp_table
%attr(0644, root, root) %verify(not md5 size mtime) %config(noreplace) %{_sysconfdir}/postfix/relocated
%attr(0644, root, root) %verify(not md5 size mtime) %config(noreplace) %{_sysconfdir}/postfix/transport
%attr(0644, root, root) %verify(not md5 size mtime) %config(noreplace) %{_sysconfdir}/postfix/virtual

#%dir %attr(-, root, root) %{_sysconfdir}/postfix/README_FILES
#%attr(0644,   root, root) %{_sysconfdir}/postfix/README_FILES/*

%attr(0755, root, root) %config /etc/rc.d/init.d/postfix

# For correct directory permissions check postfix-install script
%dir %attr(0700, postfix, root)     %verify(not md5 size mtime) %{_var}/spool/postfix/active
%dir %attr(0700, postfix, root)     %verify(not md5 size mtime) %{_var}/spool/postfix/bounce
%dir %attr(0700, postfix, root)     %verify(not md5 size mtime) %{_var}/spool/postfix/corrupt
%dir %attr(0700, postfix, root)     %verify(not md5 size mtime) %{_var}/spool/postfix/defer
%dir %attr(0700, postfix, root)     %verify(not md5 size mtime) %{_var}/spool/postfix/deferred
%dir %attr(0700, postfix, root)     %verify(not md5 size mtime) %{_var}/spool/postfix/flush
%dir %attr(0700, postfix, root)     %verify(not md5 size mtime) %{_var}/spool/postfix/incoming
%dir %attr(0700, postfix, root)     %verify(not md5 size mtime) %{_var}/spool/postfix/private
%dir %attr(0700, postfix, root)     %verify(not md5 size mtime) %{_var}/spool/postfix/saved

%dir %attr(0730, postfix, %{maildrop_group}) %verify(not md5 size mtime) %{_var}/spool/postfix/maildrop
%dir %attr(0710, postfix, %{maildrop_group}) %verify(not md5 size mtime) %{_var}/spool/postfix/public

%dir %attr(0755, root, root)        %verify(not md5 size mtime) %{_var}/spool/postfix/pid

%doc %{docdir}

%dir %attr(0755, root, root) %verify(not md5 size mtime) %{_libexecdir}/postfix
%{_libexecdir}/postfix/bounce
%{_libexecdir}/postfix/cleanup
%{_libexecdir}/postfix/error
%{_libexecdir}/postfix/flush
%{_libexecdir}/postfix/lmtp
%{_libexecdir}/postfix/local
%{_libexecdir}/postfix/master
%{_libexecdir}/postfix/nqmgr
%{_libexecdir}/postfix/pickup
%{_libexecdir}/postfix/pipe
%{_libexecdir}/postfix/proxymap
%{_libexecdir}/postfix/qmgr
%{_libexecdir}/postfix/qmqpd
%{_libexecdir}/postfix/showq
%{_libexecdir}/postfix/smtp
%{_libexecdir}/postfix/smtpd
%{_libexecdir}/postfix/spawn
%{_libexecdir}/postfix/trivial-rewrite
%{_libexecdir}/postfix/virtual

%if %{TLS}
%{_libexecdir}/postfix/tlsmgr
%endif

%{_sbindir}/postalias
%{_sbindir}/postcat
%{_sbindir}/postconf
%attr(2755,root,%{maildrop_group}) %{_sbindir}/postdrop
%attr(2755,root,%{maildrop_group}) %{_sbindir}/postqueue
%{_sbindir}/postfix
%{_sbindir}/postkick
%{_sbindir}/postlock
%{_sbindir}/postlog
%{_sbindir}/postmap
%{_sbindir}/postsuper

%{_sbindir}/smtp-sink
%{_sbindir}/smtp-source

%{_sbindir}/sendmail.postfix
%{_bindir}/mailq.postfix
%{_bindir}/newaliases.postfix
%attr(0755, root, root) %{_bindir}/rmail.postfix

%{_mandir}/*/*

%changelog
* Tue Jul 22 2003 Nalin Dahyabhai <nalin@redhat.com> 2.0.11-5
- rebuild

* Thu Jun 26 2003 John Dennis <jdennis@finch.boston.redhat.com>
- bug 98095, change rmail.postfix to rmail for uucp invocation in master.cf

* Wed Jun 25 2003 John Dennis <jdennis@finch.boston.redhat.com>
- add missing dependency for db3/db4

* Thu Jun 19 2003 John Dennis <jdennis@finch.boston.redhat.com>
- upgrade to new 2.0.11 upstream release
- fix authentication problems
- rewrite SASL documentation
- upgrade to use SASL version 2
- Fix bugs 75439, 81913 90412, 91225, 78020, 90891, 88131

* Wed Jun 04 2003 Elliot Lee <sopwith@redhat.com>
- rebuilt

* Fri Mar  7 2003 John Dennis <jdennis@finch.boston.redhat.com>
- upgrade to release 2.0.6
- remove chroot as this is now the preferred installation according to Wietse Venema, the postfix author

* Mon Feb 24 2003 Elliot Lee <sopwith@redhat.com>
- rebuilt

* Tue Feb 18 2003 Bill Nottingham <notting@redhat.com> 2:1.1.11-10
- don't copy winbind/wins nss modules, fixes #84553

* Sat Feb 01 2003 Florian La Roche <Florian.LaRoche@redhat.de>
- sanitize rpm scripts a bit

* Wed Jan 22 2003 Tim Powers <timp@redhat.com>
- rebuilt

* Sat Jan 11 2003 Karsten Hopp <karsten@redhat.de> 2:1.1.11-8
- rebuild to fix krb5.h issue

* Tue Jan  7 2003 Nalin Dahyabhai <nalin@redhat.com> 2:1.1.11-7
- rebuild

* Fri Jan  3 2003 Nalin Dahyabhai <nalin@redhat.com>
- if pkgconfig knows about openssl, use its cflags and linker flags

* Thu Dec 12 2002 Tim Powers <timp@redhat.com> 2:1.1.11-6
- lib64'ize
- build on all arches

* Wed Jul 24 2002 Karsten Hopp <karsten@redhat.de>
- make aliases.db config(noreplace) (#69612)

* Tue Jul 23 2002 Karsten Hopp <karsten@redhat.de>
- postfix has its own filelist, remove LICENSE entry from it (#69069)

* Tue Jul 16 2002 Karsten Hopp <karsten@redhat.de>
- fix shell in /etc/passwd (#68373)
- fix documentation in /etc/postfix (#65858)
- Provides: /usr/bin/newaliases (#66746)
- fix autorequires by changing /usr/local/bin/perl to /usr/bin/perl in a
  script in %%doc (#68852), although I don't think this is necessary anymore

* Mon Jul 15 2002 Phil Knirsch <pknirsch@redhat.com>
- Fixed missing smtpd.conf file for SASL support and included SASL Postfix
  Red Hat HOWTO (#62505).
- Included SASL2 support patch (#68800).

* Mon Jun 24 2002 Karsten Hopp <karsten@redhat.de>
- 1.1.11, TLS 0.8.11a
- fix #66219 and #66233 (perl required for %%post)

* Fri Jun 21 2002 Tim Powers <timp@redhat.com>
- automated rebuild

* Sun May 26 2002 Tim Powers <timp@redhat.com>
- automated rebuild

* Thu May 23 2002 Bernhard Rosenkraenzer <bero@redhat.com> 1.1.10-1
- 1.1.10, TLS 0.8.10
- Build with db4
- Enable SASL

* Mon Apr 15 2002 Bernhard Rosenkraenzer <bero@redhat.com> 1.1.7-2
- Fix bugs #62358 and #62783
- Make sure libdb-3.3.so is in the chroot jail (#62906)

* Mon Apr  8 2002 Bernhard Rosenkraenzer <bero@redhat.com> 1.1.7-1
- 1.1.7, fixes 2 critical bugs
- Make sure there's a resolv.conf in the chroot jail

* Wed Mar 27 2002 Bernhard Rosenkraenzer <bero@redhat.com> 1.1.5-3
- Add Provides: lines for alternatives stuff (#60879)

* Tue Mar 26 2002 Nalin Dahyabhai <nalin@redhat.com> 1.1.5-2
- rebuild

* Tue Mar 26 2002 Bernhard Rosenkraenzer <bero@redhat.com> 1.1.5-1
- 1.1.5 (bugfix release)
- Rebuild with current db

* Thu Mar 14 2002 Bill Nottingham <notting@redhat.com> 1.1.4-3
- remove db trigger, it's both dangerous and pointless
- clean up other triggers a little

* Wed Mar 13 2002 Bernhard Rosenkraenzer <bero@redhat.com> 1.1.4-2
- Some trigger tweaks to make absolutely sure /etc/services is in the
  chroot jail

* Mon Mar 11 2002 Bernhard Rosenkraenzer <bero@redhat.com> 1.1.4-1
- 1.1.4
- TLS 0.8.4
- Move postalias run from %%post to init script to work around
  anaconda being broken.

* Fri Mar  8 2002 Bill Nottingham <notting@redhat.com> 1.1.3-5
- use alternatives --initscript support

* Thu Feb 28 2002 Bill Nottingham <notting@redhat.com> 1.1.3-4
- run alternatives --remove in %%preun
- add various prereqs

* Thu Feb 28 2002 Nalin Dahyabhai <nalin@redhat.com> 1.1.3-3
- adjust the default postfix-files config file to match the alternatives setup
  by altering the arguments passed to post-install in the %%install phase
  (otherwise, it might point to sendmail's binaries, breaking it rather rudely)
- adjust the post-install script so that it silently uses paths which have been
  modified for use with alternatives, for upgrade cases where the postfix-files
  configuration file isn't overwritten
- don't forcefully strip files -- that's a build root policy
- remove hard requirement on openldap, library dependencies take care of it
- redirect %%postun to /dev/null
- don't remove the postfix user and group when the package is removed

* Wed Feb 20 2002 Bernhard Rosenkraenzer <bero@redhat.com> 1.1.3-2
- listen on 127.0.0.1 only by default (#60071)
- Put config samples in %{_docdir}/%{name}-%{version} rather than
  /etc/postfix (#60072)
- Some spec file cleanups

* Tue Feb 19 2002 Bernhard Rosenkraenzer <bero@redhat.com> 1.1.3-1
- 1.1.3, TLS 0.8.3
- Fix updating
- Don't run the statistics cron job
- remove requirement on perl Date::Calc

* Thu Jan 31 2002 Bernhard Rosenkraenzer <bero@redhat.com> 1.1.2-3
- Fix up alternatives stuff

* Wed Jan 30 2002 Bernhard Rosenkraenzer <bero@redhat.com> 1.1.2-2
- Use alternatives

* Sun Jan 27 2002 Bernhard Rosenkraenzer <bero@redhat.com> 1.1.2-1
- Initial Red Hat Linux packaging, based on spec file from
  Simon J Mudd <sjmudd@pobox.com>
- Changes from that:
  - Set up chroot environment in triggers to make sure we catch glibc errata
  - Remove some hacks to support building on all sorts of distributions at
    the cost of specfile readability
  - Remove postdrop group on deletion

