%define copy_cmd copy() { ln -f "$1" "$2" 2>/dev/null || cp -df "$1" "$2"; }
%define ROOT /var/spool/postfix

%define LDAP 0
%define MYSQL 0
%define PCRE 1
%define SASL 0
%define TLS 1
%define SMTPD_MULTILINE_GREETING 1
%define POSTDROP_GID 90

# If set to 1 if official version, 0 if snapshot
%define official 1 
%define ver 1.1.7
%define releasedate 20020115
%define alternatives 1
%if %{official}
Version: %{ver}
%define ftp_directory official
%else
Version: %{ver}-%{releasedate}
%define ftp_directory experimental
%endif

%define tlsno pfixtls-0.8.7-1.1.7-0.9.6c

# Postfix requires one exlusive uid/gid and a 2nd exclusive gid for its own
# use.  Let me know if the second gid collides with another package.
# Be careful: Redhat's 'mail' user & group isn't unique!
%define postfix_uid    89
%define postfix_gid    89
%define maildrop_group postdrop
%define maildrop_gid   %{POSTDROP_GID}

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
Epoch: 2
Provides: MTA smtpd smtpdaemon
Release: 1
Summary: Postfix Mail Transport Agent
Source0: ftp://ftp.porcupine.org/mirrors/postfix-release/%{ftp_directory}/%{name}-%{version}.tar.bz2
Source3: postfix-etc-init.d-postfix
Source5: postfix-aliases
Source6: postfix-chroot-setup.awk
Source9: ftp://ftp.aet.tu-cottbus.de/pub/postfix_tls/%{tlsno}.tar.bz2
Patch1: postfix-config.patch
Patch2: postfix-smtp_sasl_proto.c.patch
Patch3: postfix-alternatives.patch

# Optional patches - set the appropriate environment variables to include
#                    them when building the package/spec file

# applied if %SMTPD_MULTILINE_GREETING=1
Patch99: postfix-smtpd_multiline_greeting.patch

BuildRoot: %{_tmppath}/%{name}-buildroot

# Determine the different packages required for building postfix
BuildRequires: gawk, perl, sed, ed, db3-devel

%if %{LDAP}
BuildRequires: openldap >= 1.2.9, openldap-devel >= 1.2.9
%endif

%if %{PCRE}
Requires: pcre
BuildRequires: pcre, pcre-devel
%endif

%if %{MYSQL}
Requires: mysql, mysqlclient9
BuildRequires: mysql, mysqlclient9, mysql-devel
%endif

%if %{SASL}
Requires: cyrus-sasl
BuildRequires: cyrus-sasl, cyrus-sasl-devel
%endif

%if %{TLS}
Requires: openssl
BuildRequires: openssl-devel
%endif

Provides: /usr/sbin/sendmail /usr/bin/mailq /usr/bin/rmail

%description
Postfix is a Mail Transport Agent (MTA), supporting LDAP, SMTP AUTH (SASL),
TLS and running in a chroot environment.

%prep
umask 022

%setup -q -a 9
# Apply the TLS patch, must be at first, because the changes of master.cf
%if %{TLS}
patch -p1 <%{tlsno}/pfixtls.diff
%endif

# Apply obligatory patches
%patch1 -p1 -b .config
%patch2 -p1 -b .auth
%if %alternatives
%patch3 -p1 -b .alternatives
%endif

# Apply optional patches

# Apply my SMTPD Multiline greeting patch
%if %{SMTPD_MULTILINE_GREETING}
%patch99 -p1 -b .multiline
%endif

# Move around the TLS docs
%if %{TLS}
mkdir html/TLS
mv %{tlsno}/doc/* html/TLS
for i in ACKNOWLEDGEMENTS CHANGES INSTALL README TODO; do
  mv %{tlsno}/$i $i.TLS
done
%endif

# setup master.cf to be chrooted
mv conf/master.cf conf/master.cf-nochroot
awk -f %{_sourcedir}/postfix-chroot-setup.awk < conf/master.cf-nochroot > conf/master.cf

%build
umask 022

CCARGS=
AUXLIBS=

%ifarch s390 s390x ppc
CCARGS="${CCARGS} -fsigned-char"
%endif

%if %{LDAP}
  CCARGS="${CCARGS} -DHAS_LDAP"
  AUXLIBS="${AUXLIBS} -L/usr/lib -lldap -llber"
%endif
%if %{PCRE}
  # -I option required for pcre 3.4 (and later?)
  CCARGS="${CCARGS} -DHAS_PCRE -I/usr/include/pcre"
  AUXLIBS="${AUXLIBS} -lpcre"
%endif
%if %{MYSQL}
  CCARGS="${CCARGS} -DHAS_MYSQL -I/usr/include/mysql"
  AUXLIBS="${AUXLIBS} -L/usr/lib/mysql -lmysqlclient -lm"
%endif
%if %{SASL}
  CCARGS="${CCARGS} -DUSE_SASL_AUTH"
  AUXLIBS="${AUXLIBS} -lsasl"
%endif
%if %{TLS}
  LIBS=
  CCARGS="${CCARGS} -DHAS_SSL -I/usr/include/openssl"
  AUXLIBS="${AUXLIBS} -lssl -lcrypto"
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
       sample_directory=/samples \
       readme_directory=%{_sysconfdir}/postfix/README_FILES || exit 1

rm -fr ./samples
mv $RPM_BUILD_ROOT/samples .

# Change alias_maps and alias_database default directory to %{_sysconfdir}/postfix
bin/postconf -c $RPM_BUILD_ROOT%{_sysconfdir}/postfix -e \
	"alias_maps = hash:%{_sysconfdir}/postfix/aliases" \
	"alias_database = hash:%{_sysconfdir}/postfix/aliases" \
|| exit 1

# This installs into the /etc/rc.d/init.d directory
/bin/mkdir -p $RPM_BUILD_ROOT/etc/rc.d/init.d
install -c %{_sourcedir}/postfix-etc-init.d-postfix \
                  $RPM_BUILD_ROOT/etc/rc.d/init.d/postfix

# These set up the chroot directory structure
mkdir -p $RPM_BUILD_ROOT%{_var}/spool/postfix/etc
mkdir -p $RPM_BUILD_ROOT%{_var}/spool/postfix/lib
mkdir -p $RPM_BUILD_ROOT%{_var}/spool/postfix/usr/lib/zoneinfo

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
	sample_directory=%{_docdir}/%{name}-%{version}/samples \
	readme_directory=%{_sysconfdir}/postfix/README_FILES \
	upgrade-package

# setup chroot config
mkdir -p %{ROOT}/etc
[ -e /etc/localtime ] && cp /etc/localtime %{ROOT}/etc

%if %alternatives
/usr/sbin/alternatives --install %{_sbindir}/sendmail mta %{_sbindir}/sendmail.postfix 30 \
        --slave %{_bindir}/mailq mta-mailq %{_bindir}/mailq.postfix \
        --slave %{_bindir}/newaliases mta-newaliases %{_bindir}/newaliases.postfix \
        --slave %{_bindir}/rmail mta-rmail %{_bindir}/rmail.postfix \
        --slave %{_mandir}/man1/mailq.1.gz mta-mailqman %{_mandir}/man1/mailq.postfix.1.gz \
        --slave %{_mandir}/man1/newaliases.1.gz mta-newaliasesman %{_mandir}/man1/newaliases.postfix.1.gz \
        --slave %{_mandir}/man5/aliases.5.gz mta-aliasesman %{_mandir}/man5/aliases.postfix.5.gz \
	--initscript postfix
%endif

# Generate chroot jails on the fly when needed things are installed/upgraded
%triggerin -- glibc
%{copy_cmd}
# Kill off old versions
rm -rf %{ROOT}/lib/libnss* %{ROOT}/lib/libresolv*
# Copy the relevant parts in
LIBCVER=`ls -l /lib/libc.so.6* | sed "s/.*libc-\(.*\).so$/\1/g"`
for i in compat dns files hesiod nis nisplus winbind wins; do
	[ -e /lib/libnss_$i-${LIBCVER}.so ] && copy /lib/libnss_$i-${LIBCVER}.so %{ROOT}/lib
	[ -e /lib/libnss_$i.so ] && copy /lib/libnss_$i.so %{ROOT}/lib
done
copy /lib/libresolv-${LIBCVER}.so %{ROOT}/lib
ldconfig -n %{ROOT}/lib

%if %{LDAP}
%triggerin -- openldap
rm -rf %{ROOT}/usr/lib/liblber* %{ROOT}/usr/lib/libldap*
%{copy_cmd}
copy /usr/lib/liblber.so.2 %{ROOT}/usr/lib
copy /usr/lib/libldap_r.so.2 %{ROOT}/usr/lib
copy /usr/lib/libldap.so.2 %{ROOT}/usr/lib
ldconfig -n %{ROOT}/usr/lib
%endif

%triggerin -- setup
rm -f %{ROOT}/etc/services
%{copy_cmd}
copy /etc/services %{ROOT}/etc

%pre
# Add user and groups if necessary
%{_sbindir}/groupadd -g %{maildrop_gid} -r %{maildrop_group} 2>/dev/null || :
%{_sbindir}/groupadd -g %{postfix_gid} -r postfix 2>/dev/null || :
%{_sbindir}/useradd -d %{_var}/spool/postfix -s /bin/true -g postfix -M -r -u %{postfix_uid} postfix 2>/dev/null || :

%preun
umask 022

# selectively remove the rest of the queue directory structure
# first remove the "queues" (and assume the hash depth is still 2)
queue_directory_remove () {
    for dir in active bounce defer deferred flush incoming; do
        for a in 0 1 2 3 4 5 6 7 8 9 A B C D E F; do
   	    test -d $dir/$a && {
	        for b in 0 1 2 3 4 5 6 7 8 9 A B C D E F; do
		    test -d $dir/$a/$b && (
		        /bin/rm -f $dir/$a/$b/*
		        /bin/rmdir $dir/$a/$b
		    )
		done
		/bin/rmdir $dir/$a || echo "WARNING: preun - unable to remove directory %{_var}/spool/postfix/$dir/$a"
	    }
        done
	/bin/rmdir $dir || echo "WARNING: preun - unable to remove directory %{_var}/spool/postfix/$dir"
    done

    # now remove the other directories
    for dir in corrupt maildrop pid private public saved; do
        test -d $dir && {
            /bin/rm -f $dir/*
            /bin/rmdir $dir || echo "WARNING: preun - unable to remove directory %{_var}/spool/postfix/$dir"
        }
    done
}

if [ "$1" = 0 ]; then
    # stop postfix silently, but only if it's running
    /sbin/service postfix stop &>/dev/null
    /sbin/chkconfig --del postfix
%if %alternatives
    /usr/sbin/alternatives --remove mta %{_sbindir}/sendmail.postfix
%endif

    cd %{_var}/spool/postfix && {
        # Clean up chroot environment
	rm -rf %{ROOT}/lib %{ROOT}/usr %{ROOT}/etc
        queue_directory_remove
    }
    true # to ensure we exit safely
fi

# Remove unneeded symbolic links
for i in samples README_FILES; do
  test -L %{_sysconfdir}/postfix/$i && rm %{_sysconfdir}/postfix/$i || true
done

%postun
if [ "$1" != 0 ]; then
	/sbin/service postfix condrestart 2>&1 > /dev/null
fi
exit 0

%clean
/bin/rm -rf $RPM_BUILD_ROOT


%files
%defattr(-, root, root)
%verify(not md5 size mtime) %config %dir %{_sysconfdir}/postfix
%attr(0644, root, root)         %{_sysconfdir}/postfix/LICENSE
%attr(0755, root, root) %config %{_sysconfdir}/postfix/postfix-script
%attr(0755, root, root) %config %{_sysconfdir}/postfix/post-install
%attr(0644, root, root)                                                %{_sysconfdir}/postfix/postfix-files
%attr(0644, root, root) %verify(not md5 size mtime) %config(noreplace) %{_sysconfdir}/postfix/main.cf
%attr(0644, root, root)                                                %{_sysconfdir}/postfix/main.cf.default
%attr(0644, root, root) %verify(not md5 size mtime) %config(noreplace) %{_sysconfdir}/postfix/master.cf
%attr(0644, root, root) %verify(not md5 size mtime) %config(noreplace) %{_sysconfdir}/postfix/access
%attr(0644, root, root) %verify(not md5 size mtime) %config(noreplace) %{_sysconfdir}/postfix/aliases
%attr(0644, root, root) %verify(not md5 size mtime) %ghost             %{_sysconfdir}/postfix/aliases.db
%attr(0644, root, root) %verify(not md5 size mtime) %config(noreplace) %{_sysconfdir}/postfix/canonical
%attr(0644, root, root) %verify(not md5 size mtime) %config(noreplace) %{_sysconfdir}/postfix/pcre_table
%attr(0644, root, root) %verify(not md5 size mtime) %config(noreplace) %{_sysconfdir}/postfix/regexp_table
%attr(0644, root, root) %verify(not md5 size mtime) %config(noreplace) %{_sysconfdir}/postfix/relocated
%attr(0644, root, root) %verify(not md5 size mtime) %config(noreplace) %{_sysconfdir}/postfix/transport
%attr(0644, root, root) %verify(not md5 size mtime) %config(noreplace) %{_sysconfdir}/postfix/virtual

%dir %attr(-, root, root) %{_sysconfdir}/postfix/README_FILES
%attr(0644,   root, root) %{_sysconfdir}/postfix/README_FILES/*

%attr(0755, root, root) %config /etc/rc.d/init.d/postfix

%dir                      %verify(not md5 size mtime) %{_var}/spool/postfix
%dir %attr(-, root, root) %verify(not md5 size mtime) %{_var}/spool/postfix/etc
%dir %attr(-, root, root) %verify(not md5 size mtime) %{_var}/spool/postfix/lib
%attr(-, root, root)      %verify(not md5 size mtime) %{_var}/spool/postfix/usr

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

%doc 0README COMPATIBILITY HISTORY INSTALL LICENSE PORTING RELEASE_NOTES
%if %{TLS}
%doc ACKNOWLEDGEMENTS.TLS CHANGES.TLS README.TLS TODO.TLS html/TLS/*
%endif
%doc html
%doc samples

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

