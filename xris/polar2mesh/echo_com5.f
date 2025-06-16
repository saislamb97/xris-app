      program main

      include 'com_echo.inc'

      character *20 head,dummy    ! header information and dummy
      character *80 ifile,ofile   ! input and output files

! ==================================================
!
!     List of variables
!
!     pi: π
!
!     ifile: input  file neme
!     ofile: output file name
!
!     head:  header information, date, time and other information
!     xdir:  longitude coordinate of radar site in LatLon, not in use
!     ydir:  latitude  coordinate of radar site in LatLon, not in use
!     yt:    UTM coordinate in latitude  of radar site (zone:48N)
!     xt:    UTM coordinate in longitude of radar site (zone:48N)
!     np:    number os sweeps(shots), nodes in phase
!     nr:    number of points in radius direction nodes
!     dr:    spatial resolution in radius direction
!     oset:  offset angle of radar setting in azimuth degree
!     azi:   azimuth of every beam, in degree
!     ele:   virtical angle of every beam, in degree
!     xmp:   rainfall intensity by radar
!     rr:    UTM interpolated rainfall intensity 
!     range: radius of beam
!     eofw:  wetern end of scanning range in UTM
!     eofe:  eastern end of scanning range in UTM
!     eofs:  southern end of scanning range in UTM
!     eofn:  northern end of scanning range in UTM
!     xl:    local X-Cartesian for UTM coordinate
!     yl:    local Y-Cartesian for UTM coordinate
!



      pi=dacos(-1.d0)

! === get i/o file names from command line 
      call getarg(1,ifile)            ! get input  file name
      call getarg(2,ofile)            ! get output file name

! === input data file
      ! --- open input data file
      open(10,file=trim(ifile),status='old')      ! err routin?

      ! --- read header, date time, etc
      read(10,*)head              ! 1: date, time, scanmode?

      ! --- read coordinate of the site
      read(10,*) ydeg             ! 2: latitude  in degree (not in use)
      read(10,*) xdeg             ! 3: Longitude in degree (not in use)

      xr = 247817.59              ! longitude in UTM (zone:48N)
      yr = 238483.95              ! latitude  in UTM (zone:48N)

      ! --- read number of sweeps, beems(shots)
      read(10,*) np               ! 4. # of beams
      ! --- read number of points in radius direction
      read(10,*) nr               ! 5: # of points
      ! --- read spatial resolution in radius direction
      read(10,*) dr               ! 6: distance between points
      ! --- read phase offset of radar scanning
      read(10,*) oset             ! 7: radar off set angle
      ! --- read azimuth of beams in degree --> phase
      read(10,*) (azi(i),i=1,np)  ! 8: azimuth angles from radar off set
      !     correction of azimuth angle
      do i=1,np
        azi(i) = oset + azi(i)
        if(azi(i).lt.0)    azi(i) = azi(i) + 360.
        if(azi(i).gt.360.) azi(i) = azi(i) - 360.
      end do
      !     transfar to phase from original azimuth values
      do i=1,np
        azi(i)=450.-azi(i)                    ! to phase for all Quad.
        if(azi(i).gt.0.  and.azi(i).le.90. )  ! but in 1st Quad.
     *     azi(i)= 90.-azi(i)
      end do    
      ! --- read virtical angles of beams in degree`
      read(10,*) (ele(i),i=1,np)   ! 9: virtical angles of beam
      !     skip null data
!      read(10,*) dummy             !10: null data (for origine)
      ! --- read raifall intensity  11-end: radar data
      do i=1,nr-1                         !     radial  dierction
        read(10,*) (xmp(i,j),j=1,np)      !     azimuth direction
      end do

! === re-arrangement of sweep phase and corresponnding data
      call order

! === transfar from degree to radian of beam phase
      do i=1,np
        azi(i)= pi * azi(i)/180. ! Deg. -> Rad.
      end do


! ==============================================================
! === main routine for coordinate transfer and interpolation ===
! ==============================================================


! === set up UTM coordinate
       
! --- local Cartesian coordinnate setting
      ! === number of nodes in Cartesian (UTM) Coordinate
      ! --- set spatial resolution (unit:m)
      !reso = 10.           ! 10m
      reso = 100.           ! 10m
      ! --- range of radar for UTM
      range = nr * dr
      ! --- number of nodes (oneside of radius without center)
      nod  = int(range/reso)    ! one side (radius) without origin
      nod2 = 2*nod + 1          ! total number of points in UTM

! --- set up four cardinal in UTM for raster-GIS
      ! --- calculation of range (radius)
      utmrange = nr * dr + .5 * reso
      ! --- set four cardinal
      eofw = xr - utmrange
      eofe = xr + utmrange
      eofs = yr - utmrange
      eofn = yr + utmrange 


! === initialize interporated rainfall intensity
      do i=-nod,nod        ! nest 1 for X-Cartesian
      do j=-nod,nod        ! nest 2 for Y-Cartesian
        rr(i,j)= -1.d0
      end do               ! roop for j, nest3
      end do               ! roop for i, nest2


! === interporation of xmp at the origin (center) of polar coordinate
      sxmp=0.
      do j=1,np
        sxmp=sxmp+xmp(1,j)
      end do
      axmp0 = sxmp / np    ! interpolated value of xmp at origin

! --- set the raifall intensity value at origin in Cartesin-UTM
      rr(0,0) = axmp0

! --- set interpolated xmp at origin for polar coordinate
      do j=1, np
        xmp(0,j) = axmp0
      end do


! === azimuth interval and both boundary for azimath
      ! --- interval
      dp = 2.*pi / np                      ! phase interval, dp
      ! --- phses at both boundary
      azi(0)    = azi(1)  - dp
      azi(np+1) = azi(np) + dp
      ! --- rainfall at both phase boundary
      do i = 1,nr
        xmp(i,0) = xmp(i,np)     ! --- rainfall at left  (0)   boundary
        xmp(i,np+1) = xmp(i,1)   ! --- rainfall at right (2pi) boundary
      end do


! === interpolation of xmp
      !-----------------
      do i=-nod,nod                         ! --- West -East  direction
      do j=-nod,nod                         ! --- South-North direction
      if(i.eq.0.and.j.eq.0) goto 1000       ! origine, radar site
      ! --- local Cartesian coordinate (xl,yl)
      xl = i*reso                       ! Cartesian X-Coord.
      yl = j*reso                       ! Cartesian Y-Coord.
      ! --- local polar coordinate  (rl,pl)
      !     radius in polar coord. 
      rl = dsqrt(xl*xl+yl*yl)
      if(rl.gt.range) go to 1000        ! in case out of range, then skip
      !     phase in polar coordinate
      if(xl.gt.0.0.and.yl.ge.0.0) pl=datan( yl/xl)          ! 1st Quad
      if(xl.le.0.0.and.yl.gt.0.0) pl=datan(-xl/yl)+pi/2.    ! 2nd Quad
      if(xl.lt.0.0.and.yl.le.0.0) pl=datan( yl/xl)+pi       ! 3rd Quad
      if(xl.ge.0.0.and.yl.lt.0.0) pl=datan(-xl/yl)+3.*pi/2. ! 4th Quad
      ! --- finding lower polar points
      ir = int(rl/dr)                        ! left  node in r,P
      ip = int(pl/dp)                        ! lower node in r,p
      ! --- interpolation
      rint = (rl- ir   *dr)*(pl-azi(ip  )) * xmp(ir+1,ip+1)
     *      -(rl-(ir+1)*dr)*(pl-azi(ip  )) * xmp(ir  ,ip+1)
     *      -(rl- ir   *dr)*(pl-azi(ip+1)) * xmp(ir+1,ip  )
     *      +(rl-(ir+1)*dr)*(pl-azi(ip+1)) * xmp(ir  ,ip  )
      rint = rint / dr / dp
      rr(i,j) = rint
 1000 continue
      end do
      end do



! === make output file ====

! --- open output file
      open(20,file=trim(ofile))      ! err routin?

! --- output the result
      ! --- writing header
      write(20,650) 'north:',eofn
      write(20,650) 'south:',eofs
  650 format(a6,1x,f0.4)
      write(20,651) 'east:', eofe
      write(20,651) 'west:', eofw
  651 format(a5,1x,f0.4)
      write(20,660) 'rows:', nod2
      write(20,660) 'cols:', nod2
  660 format(a5,1x,i0)

      !--- writing data
      do j= nod,-nod,-1           ! from North to South
      do i=-nod, nod              ! from West to East
      if(i.eq.nod) then
        write(20,'(f0.3)') rr(i,j)
      else
        write(20,'(f0.3," ",$)') rr(i,j)
      end if
      end do
      end do

      close(20)


      stop
      end



!===========================================

      subroutine order

!  ascending sort of azimuth

!  local variables:
!    a:     work azimuth data (copy of original azimuth list)
!    azmin: temporal ascended azimuth list
!    xmpmin:  rainfall correspond to azmin, ipm
!==========================================

      include 'com_echo.inc'


! --- copy azi to a
      do i=1,np
        a(i) = azi(i)            ! copy azi to a
      end do

! === re-arrangement of azi, to azmin

      do j=1,np                  ! j-th smallest

! ---   find i-th smallest azimuth value
        am   = 370.
!        minj = 0
        do k=1,np
          if(a(k).lt.am) then    ! searching i-th min. azi       
            am = a(k)               ! smaller azi. 
            minj = k                ! original order of the azi
          end if
        end do

! ---   set min. azim to azmin, and remove the smallest a from a
!        if(minj.eq.0) goto 1000  ! no data souted --> skip
        azmin(j) = am            ! ordered i-th azi, azmin
        do i=1,nr                ! copy xmp correspond to ordered azim, am
          xmpmin(i,j) = xmp(i,minj)
        end do
        a(minj) = 400.           ! remove i-th min. of a, correspond to azmin
! 1000 continue

      end do

! === replacement of azim by azmin, and corresponding xmp 

      do j=1,np
        azi(j) = azmin(j)        ! replace azi by azmin
        do i=1,nr                ! replace xmp by xmpmin
          xmp(i,j) = xmpmin(i,j)
        end do
      end do
      
      return
      end

